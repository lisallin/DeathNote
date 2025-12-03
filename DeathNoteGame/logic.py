"""
logic.py

What this file does (simple version):

- This file is the "brain" of our Kira Suspicion Simulator.
- It decides how the story state changes after each player action.

Key ideas:
- We keep all important information in a GameState object, such as:
  - suspicion_L, suspicion_task_force, suspicion_public (0–100)
  - notebook_hidden (True/False)
  - l_investigation_progress (0–3)
  - location (e.g., "intro", "day_1", "caught", "victory")

- The main function is run_step(state, user_input):
  1. Read what the player typed.
  2. Classify it into an action label
     (write_name, alibi, cooperate, hide_notebook, lay_low,
      investigate_L, discover_L_name, other).
  3. Update the GameState in a fully deterministic way
     (change suspicion, progress, and location).
  4. Check if the player has:
     - lost: caught by L or the Task Force, or
     - won: either created a "new world order" or discovered L's true name.
  5. Optionally call GPT to generate a short narration of what happened.

- The important point for the project:
  All game logic and suspicion changes are controlled by this Python code.
  GPT is only used to turn the updated state into nice story text.
"""


# Standard library imports
import os  # used to read the API key from environment variables
from typing import Tuple  # used for type hints on run_step return type

# Local import: our symbolic state definition
from game_state import GameState

# OpenAI SDK import (make sure you installed it with: pip install openai)
from openai import OpenAI

# Create a client for the OpenAI API.
# It reads the key from the environment variable OPENAI_API_KEY.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# If there is no API key set, we will not call GPT.
# USE_GPT becomes True only when the key exists.
USE_GPT = os.getenv("OPENAI_API_KEY") is not None


def _clamp(x: int, lo: int = 0, hi: int = 100) -> int:
    """
    Helper function: clamp an integer x into the range [lo, hi].
    Used for keeping suspicion values within 0–100.
    """
    return max(lo, min(hi, x))


def _suspicion_summary(state: GameState) -> str:
    """
    Build a human-readable summary of the current suspicion levels
    and L-investigation progress. This is useful for debugging and
    for your milestone video.
    """
    return (
        "Suspicion levels:\n"
        f"- L: {state.suspicion_L}/100\n"
        f"- Task Force: {state.suspicion_task_force}/100\n"
        f"- Public: {state.suspicion_public}/100\n"
        f"L-investigation progress: {state.l_investigation_progress}/3\n"
    )


# ---------------- GPT NARRATION HELPERS ---------------- #

# SYSTEM_PROMPT acts as our "training data" and style guide for GPT.
# It defines:
# - The role of the model (narrator for a Kira-style game).
# - Rules for how to describe events.
# - A couple of example STATE/ACTION/INPUT -> ASSISTANT outputs.
SYSTEM_PROMPT = """
You are the narrator for an interactive fiction game inspired by Death Note.
The player is secretly Kira. Your job is to describe what happens each turn
in 1–3 short paragraphs, based on:

- The current state (location, suspicion levels, whether the notebook is hidden).
- The action label (write_name, alibi, cooperate, hide_notebook, lay_low,
  investigate_L, discover_L_name, status, other).
- The player's raw text input.

Rules:
- Never reveal exact numbers for suspicion, but it's okay to hint if suspicion is low,
  moderate, high, or dangerously high.
- Assume a genius detective similar to L is extremely smart and often becomes more
  suspicious when the player seems too helpful or too perfect.
- The Task Force is easier to reassure with alibis and public cooperation.
- The public reacts mainly to patterns in the media (many dramatic deaths raise fear
  and rumors, but they calm down when nothing happens).
- Do not mention that you are an AI or talk about prompts or system messages.
- You may occasionally include short dialogue lines in quotes.

Example 1
STATE: location=day_1, suspicion_L=35, suspicion_task_force=20, suspicion_public=10, notebook_hidden=True
ACTION: write_name
PLAYER_INPUT: "I write the name of the serial killer I just saw on TV."

ASSISTANT:
You flip open the notebook as the news anchor repeats the killer's name.
The letters feel heavier than ink as you write, imagining the cameras,
the courtroom, the smug expression that will never appear now.

Hours later, the news breaks again—this time with a sudden death.
The Task Force scrambles, and somewhere in a dark room, a pale detective
quietly updates his notes. The timing is too precise to ignore.

Example 2
STATE: location=day_1, suspicion_L=40, suspicion_task_force=15, suspicion_public=5, notebook_hidden=True
ACTION: alibi
PLAYER_INPUT: "I make sure I'm seen studying at the library."

ASSISTANT:
You arrive at the library early, making a point of greeting the staff by name.
Your laptop screen glows with mock notes while you occasionally ask loud,
boring questions about assignments.

When the next incident hits the news, the Task Force can place you
nowhere near the scene. They mark you down as cooperative and studious—
but somewhere behind a monitor, a single set of eyes underlines your name twice.
"""


def _state_to_text(state: GameState) -> str:
    """
    Serialize important parts of state into a compact string that we
    pass to GPT. This lets the model know the current situation.
    """
    return (
        f"location={state.location}, "
        f"suspicion_L={state.suspicion_L}, "
        f"suspicion_task_force={state.suspicion_task_force}, "
        f"suspicion_public={state.suspicion_public}, "
        f"notebook_hidden={state.notebook_hidden}, "
        f"l_investigation_progress={state.l_investigation_progress}"
    )


def generate_narration(state: GameState, user_input: str, action_label: str) -> str:
    """
    Call GPT to generate a narrative paragraph based on:
    - the current symbolic state (converted to text),
    - the player's raw input,
    - the abstract action label we detected.

    Returns the string narration from the model.
    """
    # Convert the GameState into a single string line for the prompt
    state_text = _state_to_text(state)

    # Construct the chat messages:
    # - system: contains the rules and examples
    # - user: contains the current STATE/ACTION/PLAYER_INPUT triple
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"STATE: {state_text}\n"
                f"ACTION: {action_label}\n"
                f"PLAYER_INPUT: {user_input}\n\n"
                "Write the next bit of narration."
            ),
        },
    ]

    # Call the Chat Completions API
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",   # model name (can be swapped to another compatible model)
        messages=messages,      # the messages array we built above
        temperature=0.8,        # some randomness for creative narration
        max_tokens=350,         # limit on narration length
    )

    # Extract the text content from the first choice of the response
    return completion.choices[0].message.content.strip()


# ---------------- MAIN GAME LOGIC ---------------- #

def run_step(state: GameState, user_input: str) -> Tuple[GameState, str]:
    """
    Core logic for the Kira suspicion demo.

    Steps:
    - Increment turn and log the input.
    - Map the text to an action label.
    - Update the state (suspicion, flags, location).
    - Check for win or lose conditions.
    - Ask GPT for narration (if enabled) or use a fallback text.
    - Return updated state and the system_output string.

    Terminal states:
    - state.location == "caught"   -> lose (Kira exposed)
    - state.location == "victory"  -> win (either new world order or L-name route)
    """

    # Increase the turn count each time we get an input
    state.turn += 1

    # Record the player's message in the history
    state.history.append({"user": user_input})

    # Normalize the input for easier substring checks
    text = user_input.lower().strip()

    # Default action label: "other" (used when no specific pattern matches)
    action_label = "other"

    # ---------- Early exits: already in a terminal state ---------- #

    # If the player has already been caught, don't update state further
    if state.location == "caught":
        system_output = (
            "You have already been exposed as Kira.\n"
            "Use the Reset button to start a new timeline."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # If the player already reached victory, keep state frozen
    if state.location == "victory":
        system_output = (
            "You have already reshaped this timeline according to your will.\n"
            "The investigation is over; this world belongs to Kira.\n"
            "Use the Reset button if you want to attempt a different path."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Intro phase: only happens once at the beginning ---------- #

    if state.location == "intro":
        # Provide a fixed intro description (no GPT here, to keep it deterministic)
        system_output = (
            "You are secretly Kira, armed with a supernatural notebook.\n"
            "A brilliant detective and a dedicated Task Force suspect that Kira "
            "is hiding in your city, but they don't know it's you yet.\n\n"
            "Type what you want to do each turn. For example:\n"
            "- 'write a criminal's name'\n"
            "- 'cooperate with the investigation'\n"
            "- 'create an alibi'\n"
            "- 'lay low'\n"
            "- 'investigate L'\n"
            "- 'status' to see suspicion levels\n\n"
            "Your goal is to use the notebook without letting suspicion reach 100, "
            "or to uncover the detective's true name before they catch you."
        )
        # Move to the main phase of the story
        state.location = "day_1"
        # Record system output in history and return
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Status command: show numeric state (no GPT needed) ---------- #

    if text == "status":
        # Build a textual summary using the helper
        system_output = _suspicion_summary(state)
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Action branches that change suspicion and progress ---------- #

    # Using the notebook to write someone's name
    if "write" in text and "name" in text:
        action_label = "write_name"
        # Notebook hidden status stays the same (but logic is here if you want to change it later)
        state.notebook_hidden = state.notebook_hidden
        # Aggressive use of the notebook makes L and the Task Force suspicious, and affects the public
        state.suspicion_L = _clamp(state.suspicion_L + 15)
        state.suspicion_task_force = _clamp(state.suspicion_task_force + 10)
        state.suspicion_public = _clamp(state.suspicion_public + 5)

    # Creating an alibi or covering your tracks
    elif any(k in text for k in ["alibi", "cover", "lie", "excuse"]):
        action_label = "alibi"
        # These actions reduce suspicion for the Task Force and the public...
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 8)
        state.suspicion_public = _clamp(state.suspicion_public - 3)
        # ...but increase suspicion for the genius detective
        state.suspicion_L = _clamp(state.suspicion_L + 3)

    # Cooperating with / helping the investigation
    elif ("cooperate" in text) or ("help" in text and "investigation" in text):
        action_label = "cooperate"
        # Cooperation lowers public and Task Force suspicion...
        state.suspicion_public = _clamp(state.suspicion_public - 5)
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 5)
        # ...but makes the detective more suspicious (why are you so helpful?)
        state.suspicion_L = _clamp(state.suspicion_L + 5)

    # Hiding or relocating the notebook
    elif "hide" in text or "move the notebook" in text or "relocate" in text:
        action_label = "hide_notebook"
        # If the notebook is currently not hidden, hide it
        if not state.notebook_hidden:
            state.notebook_hidden = True
        # Even careful actions create a small suspicion drift
        state.suspicion_L = _clamp(state.suspicion_L + 1)

    # Laying low and doing nothing
    elif "lay low" in text or "do nothing" in text or "stay quiet" in text:
        action_label = "lay_low"
        # Laying low reduces suspicion a little bit
        state.suspicion_L = _clamp(state.suspicion_L - 3)
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 2)

    # Investigating L to build progress towards discovering their name
    elif any(
        phrase in text
        for phrase in [
            "investigate l",
            "study l",
            "research l",
            "analyze l",
            "look into l",
            "learn about l",
        ]
    ):
        action_label = "investigate_L"
        # Each investigation step increases progress, up to a maximum of 3
        state.l_investigation_progress = min(3, state.l_investigation_progress + 1)
        # But poking around L raises suspicion
        state.suspicion_L = _clamp(state.suspicion_L + 6)
        state.suspicion_task_force = _clamp(state.suspicion_task_force + 3)

    # Trying to discover L's true name (hard, gated win condition)
    elif any(
        phrase in text
        for phrase in [
            "l's real name",
            "l's true name",
            "find l's name",
            "learn l's name",
            "discover l's name",
            "figure out l's name",
            "know l's name",
        ]
    ):
        action_label = "discover_L_name"

        # Conditions to succeed:
        # - at least 3 investigation steps
        # - at least 6 turns into the story
        # - L's suspicion not extremely high
        if (
            state.l_investigation_progress >= 3
            and state.turn >= 6
            and state.suspicion_L <= 70
        ):
            # Mark that we know L's name and enter the victory state
            state.flags["l_name_known"] = True
            state.location = "victory"
            system_output = (
                _suspicion_summary(state)
                + "\nThrough careful manipulation, observation, and calculated risks, "
                  "you finally piece together the detective's true identity.\n"
                  "A real name replaces a single letter in your mind.\n\n"
                  "With that name, the balance of power is no longer equal. "
                  "The one person who could truly corner you is now exposed to the same "
                  "silent judgment as everyone else.\n"
                  "Whether you write it down or not, this world already belongs to Kira.\n"
                  "Use the Reset button if you want to attempt a different fate."
            )
            state.history.append({"system": system_output})
            return state, system_output
        else:
            # If conditions are not met, the attempt fails and drastically raises suspicion
            state.suspicion_L = _clamp(state.suspicion_L + 20)
            state.suspicion_task_force = _clamp(state.suspicion_task_force + 10)
            system_output = (
                _suspicion_summary(state)
                + "\nYou reach too far, too soon.\n"
                  "Your attempts to pry into the detective's identity hit hardened walls—"
                  "fake backgrounds, dead ends, and suddenly watchful eyes.\n"
                  "Someone on the other side tightens their grip on the investigation.\n"
                  "If you want their name, you'll need more subtle groundwork first."
            )
            state.history.append({"system": system_output})
            return state, system_output

    # Help command: print available actions
    elif text == "help":
        system_output = (
            "Commands you can try:\n"
            "- 'write a name' to use the notebook\n"
            "- 'create an alibi' or 'cover my tracks'\n"
            "- 'cooperate with the investigation'\n"
            "- 'lay low' or 'do nothing'\n"
            "- 'hide the notebook'\n"
            "- 'investigate L' to carefully study the detective (build progress)\n"
            "- later, attempt to 'find L's name' if you think you're ready\n"
            "- 'status' to see suspicion levels and L-investigation progress\n"
        )
        state.history.append({"system": system_output})
        return state, system_output

    # Generic fallback: ambiguous action
    else:
        action_label = "other"
        # Slight suspicion increase because ambiguous behavior can still be weird
        state.suspicion_L = _clamp(state.suspicion_L + 2)

    # ---------- Check for win / lose conditions before narration ---------- #

    # WIN CONDITION A: Kira reshapes the world (new world order)
    if (
        state.suspicion_public >= 80
        and state.suspicion_L <= 40
        and state.suspicion_task_force <= 40
        and state.turn >= 8
    ):
        state.location = "victory"
        system_output = (
            _suspicion_summary(state)
            + "\nThe world tilts in your favor.\n"
              "Fear, awe, and a twisted sense of safety spread through the public.\n"
              "Crime plummets, and people begin to speak of an invisible judge\n"
              "who punishes evil and spares the obedient.\n\n"
              "The investigation has names and theories, but nothing that can touch you.\n"
              "In this timeline, you have become the architect of a new order.\n"
              "Use the Reset button if you want to attempt a different path."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # LOSE CONDITION: L or Task Force reaches full suspicion
    if state.suspicion_L >= 100 or state.suspicion_task_force >= 100:
        state.location = "caught"
        system_output = (
            _suspicion_summary(state)
            + "\nAlarms ring through the Task Force headquarters.\n"
              "Your patterns, your alibis, and your timing all point in one direction.\n"
              "They confront you with the evidence—cold eyes and a quiet, final question.\n"
              "You have been exposed as the killer. Game over.\n"
              "Use the Reset button to start a new timeline."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Use GPT if available, otherwise a simple fallback ---------- #

    if USE_GPT:
        try:
            # Ask the model to generate narration based on the updated state
            narrative = generate_narration(state, user_input, action_label)
            # Add a [GPT] tag so you can see in the UI that the model was used
            system_output = "[GPT]\n" + narrative + "\n\n" + _suspicion_summary(state)
        except Exception as e:
            # If anything goes wrong with the API, show an error and still show state
            system_output = (
                "[GPT ERROR] The narration engine failed.\n"
                f"(Error: {e})\n\n"
                + _suspicion_summary(state)
            )
    else:
        # Non-GPT fallback so the game still runs without an API key
        system_output = (
            "[NO GPT]\n"
            f"You act: '{user_input}'. Suspicion and state are updated.\n\n"
            + _suspicion_summary(state)
        )

    # Record the system output in history and return the updated state + text
    state.history.append({"system": system_output})
    return state, system_output
