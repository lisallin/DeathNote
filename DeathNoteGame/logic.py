"""
logic.py

Simple summary for the video/report:

- This file is the "brain" of our Kira Suspicion Simulator.
- It decides how the game state changes after each player action.

Key ideas:
- We keep the full game in a GameState object (turn, location, suspicion levels,
  progress investigating L, camera flags, etc.).
- The main function is run_step(state, user_input):
  1. Read what the player typed.
  2. Map it to an action label (write_name, alibi, cooperate, lay_low,
     move_home, move_school, investigate_L, discover_L_name, watch_tv, etc.).
  3. Update the GameState in a deterministic way (change suspicion, location).
  4. Check win/lose conditions.
  5. Call GPT to write a short narration based on the new state.
- All rules, suspicion changes, and endings are in this Python file.
  GPT is only used to turn the state into story text.
"""

import os
import random
from typing import Tuple

from game_state import GameState
from openai import OpenAI

# OpenAI client – uses the OPENAI_API_KEY environment variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Flag keys
TV_TARGET_FLAG = "tv_target_ready"
SECOND_KIRA_REVEALED_FLAG = "second_kira_revealed"
SECOND_KIRA_FRIEND_FLAG = "second_kira_friend"

# Some placeholder criminal names for flavor when TV shows a target
CRIMINAL_NAMES = [
    "Hideo Takahashi",
    "Mika Tanaka",
    "Daisuke Mori",
    "Ryoji Nakamura",
    "Kazuo Arai",
]


def _clamp(x: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp an integer into [lo, hi]."""
    return max(lo, min(hi, x))


def _suspicion_summary(state: GameState) -> str:
    """
    Short debug summary for the status command.
    Includes location and whether cameras have been noticed.
    """
    camera_text = "no known cameras at home"
    if state.cameras_revealed_to_player:
        camera_text = "hidden cameras detected at home"

    return (
        f"Current location: {state.location}\n"
        f"Home security: {camera_text}\n"
        "Suspicion levels:\n"
        f"- L: {state.suspicion_L}/100\n"
        f"- Task Force: {state.suspicion_task_force}/100\n"
        f"L-investigation progress: {state.l_investigation_progress}/3\n"
    )


# ---------------- GPT NARRATION HELPERS ---------------- #

SYSTEM_PROMPT = """
You are the narrator for an interactive fiction game closely inspired by the
early episodes of the anime Death Note (the Light vs L arc).

The player is secretly Kira: a brilliant student living with their family in
modern Japan. On the surface, they have just agreed to cooperate with L and
the Task Force to help "catch Kira," while hiding the fact that they are Kira.

Your job is to describe what happens each turn in 1–3 short paragraphs,
based on:

- The current state (location, suspicion levels, cameras at home, etc.).
- The action label (write_name, write_name_without_tv, watch_tv, alibi,
  cooperate, hide_notebook, lay_low, move_home, move_school,
  move_task_force_hq, move_downtown, investigate_L, discover_L_name,
  befriend_second_kira, look_around, status, other).
- The player's raw text input.

The STATE string may also contain:
- second_kira_revealed=True/False → the Task Force and the player know there
  is a "second Kira" from a TV broadcast.
- second_kira_friend=True/False → the player has quietly formed an alliance
  with the second Kira.

Tone & style:
- Make it feel like a tense episode of Death Note: a quiet cat-and-mouse game
  between Kira and L, with lots of inner tension and subtle dread.
- Focus on what a Light-like Kira does and how L and the Task Force react in
  the background: surveillance, deductions, late-night meetings.
- Keep it grounded in modern Japan: news broadcasts, cram school, police HQ,
  press conferences, TV in classrooms, crowded city streets.

Suspicion logic (how to talk about it):
- You will see suspicion_L and suspicion_task_force (0–100).
- Never say the exact numbers; only words like:
  low / moderate / high / dangerous / on the verge.
- Rough mapping for your descriptions:
  - 0–30  → low
  - 31–60 → moderate
  - 61–80 → high
  - 81–100 → dangerous / on the verge
- When suspicion_L is low, L has only vague theories and watches from afar.
- When suspicion_L is moderate, hint that L is narrowing his list:
  focusing on students, police families, time-of-day patterns.
- When suspicion_L is high, L actively targets the player:
  hidden cameras like in the Yagami house, tailing, specific tests and traps.
- When suspicion_L is dangerous, describe L as almost ready to accuse or arrest,
  matching death patterns to the player’s movements.
- The Task Force is easier to reassure with alibis and cooperation, but they
  can still be convinced if the timing is too perfect or too convenient.

Location flavor:
- home: Feels like Light’s bedroom. If cameras_at_home is true, home scenes
  should feel watched and unsafe whenever the notebook is even mentioned.
- school: Ordinary student life on the surface; classmates gossip about Kira,
  teachers leave the news on, rumors spread in the hallways.
- task_force_hq: A secretive base where L and the Task Force analyze data.
  The player must act extra careful and helpful here.
- downtown: Anonymous crowds, TVs in shop windows, random people debating
  whether Kira is justice or a monster.

Special game rule – TV prerequisite:
- The field tv_target_ready in STATE tells you if the player has recently
  watched a TV or public screen and has a fresh target from a broadcast.
- tv_target_ready can become true either when the player explicitly watches TV
  or when they happen to see a criminal's face and name on a public screen
  while moving between locations.
- If tv_target_ready is False and ACTION is write_name or write_name_without_tv:
  no one dies this turn. Describe hesitation, lack of a clear target, or the
  player realizing they need a name and face from a broadcast first.
- If tv_target_ready is True and ACTION is write_name:
  you may describe a successful Kira-style killing, usually tied to something
  the player would have just seen on TV or a screen. After that, assume
  tv_target_ready will be False again on the next turn.

General rules:
- L is extremely smart and often becomes more suspicious when the player looks
  too perfect or too eager to help.
- Subtlety is better than explosions: focus on glances, pauses, and quiet
  realizations more than action scenes.
- If second_kira_friend is True, the player and second Kira cooperate in a
  dangerous, unstable way that sometimes helps them read L's behavior.
- Do not talk about prompts, system messages, or that you are an AI.
- Do not contradict the given state; instead, interpret and dramatize it like
  a Death Note episode.
"""


def _state_to_text(state: GameState) -> str:
    """Serialize key parts of state into one line for GPT."""
    tv_ready = bool(state.flags.get(TV_TARGET_FLAG, False))
    second_seen = bool(state.flags.get(SECOND_KIRA_REVEALED_FLAG, False))
    second_friend = bool(state.flags.get(SECOND_KIRA_FRIEND_FLAG, False))
    return (
        f"location={state.location}, "
        f"suspicion_L={state.suspicion_L}, "
        f"suspicion_task_force={state.suspicion_task_force}, "
        f"notebook_hidden={state.notebook_hidden}, "
        f"l_investigation_progress={state.l_investigation_progress}, "
        f"cameras_at_home={state.cameras_at_home}, "
        f"tv_target_ready={tv_ready}, "
        f"second_kira_revealed={second_seen}, "
        f"second_kira_friend={second_friend}"
    )


def generate_narration(state: GameState, user_input: str, action_label: str) -> str:
    """Call GPT to generate a narrative paragraph."""
    state_text = _state_to_text(state)

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

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.8,
        max_tokens=350,
    )

    return completion.choices[0].message.content.strip()


# ------------- RANDOM TV TARGET HELPER ------------- #

def _maybe_grant_tv_target(state: GameState, event_messages: list) -> None:
    """
    Small chance to see a criminal on TV when moving between locations.

    If tv_target_ready is False and the random roll succeeds, we:
    - pick a random criminal name
    - set TV_TARGET_FLAG to True
    - append an event message telling the player they now have a usable target
    """
    if state.flags.get(TV_TARGET_FLAG, False):
        return  # already have a target

    # ~35% chance each time you move
    if random.random() < 0.35:
        state.flags[TV_TARGET_FLAG] = True
        name = random.choice(CRIMINAL_NAMES)

        # Location-flavored description
        if state.location == "home":
            place = "a news report on the living room TV"
        elif state.location == "school":
            place = "a TV left on in the school hallway"
        elif state.location == "task_force_hq":
            place = "a muted news feed playing in the Task Force's lobby"
        else:  # downtown
            place = "a row of bright TVs in a shop window"

        msg = (
            f"As you move, {place} catches your eye.\n"
            f"The anchors repeat the name and show the face of a wanted criminal: {name}.\n"
            "You now have a clear name and face in mind—you could write this person in the notebook."
        )
        event_messages.append(msg)


# ---------------- MAIN GAME LOGIC ---------------- #

def run_step(state: GameState, user_input: str) -> Tuple[GameState, str]:
    """
    Core logic for one player action.
    Updates the GameState and returns (state, system_output_text).
    """

    state.turn += 1
    state.history.append({"user": user_input})

    text = user_input.lower().strip()
    action_label = "other"

    # special event messages we might attach to the response
    event_messages: list[str] = []

    # Should we clear the TV target *after* narration?
    consume_tv_target_after = False

    # ---------- Terminal states: already caught / victory ---------- #

    if state.location == "caught":
        system_output = (
            "You have already been exposed as Kira.\n"
            "Use the Reset button to start a new timeline."
        )
        state.history.append({"system": system_output})
        return state, system_output

    if state.location == "victory":
        system_output = (
            "You have already reshaped this timeline according to your will.\n"
            "Use the Reset button if you want to attempt a different path."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Intro / welcome screen ---------- #

    if state.location == "intro":
        system_output = (
            "Welcome to the Kira Suspicion Simulator.\n\n"
            "You are secretly Kira, using a supernatural notebook that can kill.\n"
            "Publicly, you have just agreed to work with L and the Task Force to help\n"
            "catch 'Kira'—without letting anyone realize that Kira is you.\n\n"
            "In this version of the story, you can only write a name after you've\n"
            "recently watched a TV or public screen and seen someone's face and name.\n\n"
            "Type what you want to do each turn. For example:\n"
            "- 'watch tv' or 'watch the news'\n"
            "- 'write a criminal's name' (after watching a screen)\n"
            "- 'look around' to see where you can move\n"
            "- 'cooperate with the investigation'\n"
            "- 'create an alibi'\n"
            "- 'lay low'\n"
            "- 'investigate L'\n"
            "- move: 'go home', 'go to school', 'go to task force hq', 'go downtown'\n"
            "- 'status' to see location and suspicion levels\n\n"
            "Your goal is to use the notebook without letting suspicion reach 100,\n"
            "or to uncover the detective's true name before he catches you."
        )
        # after intro, start at home
        state.location = "home"
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Status command ---------- #

    if text == "status":
        system_output = _suspicion_summary(state)
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Look around: list possible moves ---------- #

    if text in ["look", "look around", "look around the room", "where can i go"]:
        action_label = "look_around"
        system_output = (
            f"You look around. Right now you are at: {state.location}.\n\n"
            "From here, you can move to:\n"
            "- home\n"
            "- school\n"
            "- task force hq\n"
            "- downtown\n\n"
            "Use commands like 'go home', 'go to school', "
            "'go to task force hq', or 'go downtown'."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- Action branches ---------- #

    # Use the notebook (requires recent TV/screen target)
    if "write" in text and "name" in text:
        if not state.flags.get(TV_TARGET_FLAG, False):
            # Attempt to write without a fresh TV target – blocked
            action_label = "write_name_without_tv"
            # Slight increase in L suspicion: patterns of hesitation / fewer deaths
            state.suspicion_L = _clamp(state.suspicion_L + 1)
            event_messages.append(
                "You reach for the notebook, but you have no fresh name and face from a broadcast.\n"
                "In this timeline, the notebook only answers when your target has just been paraded "
                "across a screen. For now, the pages stay still."
            )
        else:
            action_label = "write_name"
            # Mark that we should consume the TV target *after* narration
            consume_tv_target_after = True

            # base suspicion changes (actual kill happens)
            state.suspicion_L = _clamp(state.suspicion_L + 8)
            state.suspicion_task_force = _clamp(state.suspicion_task_force + 5)

            # EXTRA RISK: at home with cameras
            if state.location == "home" and state.cameras_at_home:
                state.suspicion_L = _clamp(state.suspicion_L + 10)
                state.suspicion_task_force = _clamp(
                    state.suspicion_task_force + 10
                )

    # Watch TV / screen to get a target
    elif any(
        phrase in text
        for phrase in [
            "watch tv",
            "watch the tv",
            "turn on tv",
            "turn on the tv",
            "watch the news",
            "watch news",
            "check the news",
            "look at the tv",
            "look at tv",
            "look at the screen",
            "watch the screen",
            "watch a screen",
        ]
    ):
        action_label = "watch_tv"
        state.flags[TV_TARGET_FLAG] = True

        # Very small suspicion bump – L may later correlate broadcasts and deaths
        state.suspicion_L = _clamp(state.suspicion_L + 1)
        state.suspicion_task_force = _clamp(state.suspicion_task_force + 1)

    # Create an alibi / cover tracks
    elif any(k in text for k in ["alibi", "cover", "lie", "excuse"]):
        action_label = "alibi"
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 6)
        state.suspicion_L = _clamp(state.suspicion_L + 2)

    # Cooperate with investigation
    elif ("cooperate" in text) or ("help" in text and "investigation" in text):
        action_label = "cooperate"
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 4)
        state.suspicion_L = _clamp(state.suspicion_L + 3)

    # Hide notebook
    elif "hide" in text or "move the notebook" in text or "relocate" in text:
        action_label = "hide_notebook"
        if not state.notebook_hidden:
            state.notebook_hidden = True
        state.suspicion_L = _clamp(state.suspicion_L + 1)

    # Lay low
    elif "lay low" in text or "do nothing" in text or "stay quiet" in text:
        action_label = "lay_low"
        state.suspicion_L = _clamp(state.suspicion_L - 2)
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 1)

    # ---------- Moving between locations ---------- #

    elif any(
        phrase in text
        for phrase in [
            "go home",
            "return home",
            "back home",
            "to my room",
            "to my house",
        ]
    ):
        action_label = "move_home"
        state.location = "home"
        state.suspicion_L = _clamp(state.suspicion_L - 1)
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 1)
        _maybe_grant_tv_target(state, event_messages)

    elif any(
        phrase in text
        for phrase in [
            "go to school",
            "go to class",
            "go to campus",
            "to school",
        ]
    ):
        action_label = "move_school"
        state.location = "school"
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 1)
        _maybe_grant_tv_target(state, event_messages)

    elif any(
        phrase in text
        for phrase in [
            "task force hq",
            "go to hq",
            "go to task force",
            "meet the task force",
            "go to police",
        ]
    ):
        action_label = "move_task_force_hq"
        state.location = "task_force_hq"
        state.suspicion_task_force = _clamp(state.suspicion_task_force - 2)
        state.suspicion_L = _clamp(state.suspicion_L + 2)
        _maybe_grant_tv_target(state, event_messages)

    elif any(
        phrase in text
        for phrase in [
            "go downtown",
            "go outside",
            "go into the city",
            "walk around town",
            "go out",
        ]
    ):
        action_label = "move_downtown"
        state.location = "downtown"
        _maybe_grant_tv_target(state, event_messages)

    # Investigate L (only allowed at task_force_hq, with 40% failure chance)
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

        # Must be at Task Force HQ to really investigate L
        if state.location != "task_force_hq":
            event_messages.append(
                "You try to piece together information about L from here, "
                "but without direct access to the Task Force data at headquarters "
                "it's mostly rumors and guesswork.\n"
                "If you want to truly investigate L, you should go to task force hq first."
            )
        else:
            # At HQ: 40% chance this attempt FAILS and spikes L's suspicion
            if random.random() < 0.50:
                # Failure: no progress, big suspicion jump for L
                state.suspicion_L = _clamp(state.suspicion_L + 30)
                event_messages.append(
                    "At headquarters, you push a little too hard for details about L himself.\n"
                    "Your questions linger in the air a bit too long, and you catch the way "
                    "L's eyes rest on you.\n"
                    "This attempt to investigate him backfires—his suspicion of you spikes sharply."
                )
            else:
                # Success: normal investigation effects
                state.l_investigation_progress = min(
                    3, state.l_investigation_progress + 1
                )
                state.suspicion_L = _clamp(state.suspicion_L + 5)
                state.suspicion_task_force = _clamp(state.suspicion_task_force + 3)

                # Special one-time TV event that reveals a second Kira
                if not state.flags.get(SECOND_KIRA_REVEALED_FLAG, False):
                    state.flags[SECOND_KIRA_REVEALED_FLAG] = True
                    event_messages.append(
                        "While you're reviewing case files with the Task Force, a breaking-news banner "
                        "cuts across the TV in the corner.\n"
                        "A distorted voice claiming to be 'Kira' appears, demanding to speak directly "
                        "with L. The style is theatrical and reckless—nothing like the careful pattern "
                        "you've established.\n"
                        "On screen and in the room, people start whispering about a 'second Kira' who "
                        "may share your power but not your caution.\n"
                        "If you can quietly befriend this second Kira, they might help you read how L "
                        "reacts to new threats.\n"
                        "Try commands like 'befriend second kira' or 'ally with the second kira'."
                    )

    # Befriend the second Kira (only after the TV reveal)
    elif any(
        phrase in text
        for phrase in [
            "befriend second kira",
            "ally with second kira",
            "ally with the second kira",
            "contact second kira",
            "meet second kira",
            "work with second kira",
        ]
    ):
        action_label = "befriend_second_kira"

        if not state.flags.get(SECOND_KIRA_REVEALED_FLAG, False):
            event_messages.append(
                "You hear nothing but rumors. If there is a second Kira, you haven't seen enough "
                "to reach them yet. Maybe you should investigate L at task force hq first."
            )
        elif state.flags.get(SECOND_KIRA_FRIEND_FLAG, False):
            event_messages.append(
                "Your fragile alliance with the second Kira is already in place. For now you both "
                "keep your distance and watch how L responds."
            )
        else:
            state.flags[SECOND_KIRA_FRIEND_FLAG] = True
            # Second Kira's help gives you more insight into L
            state.l_investigation_progress = min(
                3, state.l_investigation_progress + 1
            )
            # But coordinated weird behavior also raises suspicion
            state.suspicion_L = _clamp(state.suspicion_L + 4)
            state.suspicion_task_force = _clamp(state.suspicion_task_force + 2)
            event_messages.append(
                "Through carefully coded messages, you manage to reach the second Kira.\n"
                "They are impulsive and eager to please, willing to act just to see how L reacts.\n"
                "By nudging their actions, you gain a clearer view of L's methods and timing.\n"
                "Your understanding of L deepens (+1 L-investigation progress), but the "
                "case also becomes stranger and harder to hide."
            )

    # Try to discover L's real name
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

        if (
            state.l_investigation_progress >= 3
            and state.turn >= 6
            and state.suspicion_L <= 70
        ):
            state.flags["l_name_known"] = True
            state.location = "victory"
            system_output = (
                _suspicion_summary(state)
                + "\nThrough careful investigation and controlled risks, "
                  "you finally piece together the detective's true identity.\n"
                  "With his real name in your hands, the one person who could "
                  "truly corner you is no longer untouchable.\n"
                  "This timeline now belongs to Kira.\n"
                  "Use Reset if you want to explore a different path."
            )
            state.history.append({"system": system_output})
            return state, system_output
        else:
            state.suspicion_L = _clamp(state.suspicion_L + 12)
            state.suspicion_task_force = _clamp(state.suspicion_task_force + 8)
            system_output = (
                _suspicion_summary(state)
                + "\nYou reach too far, too soon.\n"
                  "Your attempts to uncover L's identity run into fake records "
                  "and suddenly watchful eyes.\n"
                  "If you want his name, you need more groundwork first."
            )
            state.history.append({"system": system_output})
            return state, system_output

    # Help
    elif text == "help":
        system_output = (
            "Commands you can try:\n"
            "- 'watch tv' or 'watch the news' to get a target\n"
            "- 'write a name' to use the notebook (only after watching a screen)\n"
            "- 'look around' to see where you can move\n"
            "- 'create an alibi' or 'cover my tracks'\n"
            "- 'cooperate with the investigation'\n"
            "- 'lay low' or 'do nothing'\n"
            "- 'hide the notebook'\n"
            "- 'investigate L' at task force hq to build progress (may reveal a second Kira, "
            "but sometimes backfires and sharply raises L's suspicion)\n"
            "- after the TV reveal: 'befriend second kira' to try forming an alliance\n"
            "- move: 'go home', 'go to school', 'go to task force hq', 'go downtown'\n"
            "- later: try to find L's name when you think you're ready\n"
            "- 'status' to see location, cameras, and suspicion levels\n"
        )
        state.history.append({"system": system_output})
        return state, system_output

    # Fallback
    else:
        action_label = "other"
        state.suspicion_L = _clamp(state.suspicion_L + 1)

    # ---------- Location-based event: cameras at home ---------- #

    if (
        state.location == "home"
        and state.suspicion_L >= 50
        and not state.cameras_at_home
    ):
        state.cameras_at_home = True
        state.cameras_revealed_to_player = True
        event_messages.append(
            "When you settle back into your room, something feels wrong.\n"
            "A faint click from the ceiling, a lens glint near the bookshelf—"
            "someone has installed hidden cameras in your home.\n"
            "Using the notebook here is now extremely risky."
        )

    # ---------- Win / lose checks ---------- #

    # Win path A – "new world order" with low suspicion
    if (
        state.suspicion_L <= 40
        and state.suspicion_task_force <= 40
        and state.turn >= 10
    ):
        state.location = "victory"
        system_output = (
            _suspicion_summary(state)
            + "\nThe world tilts in your favor.\n"
              "Deaths continue to follow the pattern you choose, but L and the Task\n"
              "Force never quite manage to pin them on you. You remain their ally\n"
              "on paper and their god in secret.\n"
              "Use Reset if you want to attempt a different path."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # Lose – L or Task Force reach 100 suspicion
    if state.suspicion_L >= 100 or state.suspicion_task_force >= 100:
        state.location = "caught"
        system_output = (
            _suspicion_summary(state)
            + "\nThe pieces finally line up.\n"
              "Your movements, alibis, and timing all converge on one conclusion.\n"
              "You are confronted with the evidence and quietly cornered.\n"
              "You have been exposed as Kira. Game over.\n"
              "Use Reset to start a new timeline."
        )
        state.history.append({"system": system_output})
        return state, system_output

    # ---------- GPT narration ---------- #

    narrative = generate_narration(state, user_input, action_label)
    system_output = "[GPT]\n" + narrative

    if event_messages:
        system_output = "\n\n".join(event_messages + [system_output])

    # Now that narration is done, actually consume the TV target if needed
    if consume_tv_target_after:
        state.flags[TV_TARGET_FLAG] = False

    # (No extra suspicion summary here – that's in status/debug/ending.)
    state.history.append({"system": system_output})
    return state, system_output
