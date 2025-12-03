// This function sends the user's text to the backend /api/step endpoint
async function sendInput(userText) {
  // Call the backend using fetch with a POST request
  const res = await fetch("/api/step", {
    // HTTP method
    method: "POST",
    // Tell the server we are sending JSON
    headers: { "Content-Type": "application/json" },
    // Convert our JavaScript object into a JSON string as the request body
    body: JSON.stringify({ user_input: userText })
  });

  // Wait for the server to send back JSON and parse it
  const data = await res.json();

  // If the server returned an error field, show an alert and stop
  if (data.error) {
    alert(data.error);
    return;
  }

  // Get the message log div element
  const log = document.getElementById("log");

  // Append the user's message to the log (with a "user" CSS class)
  log.innerHTML += `<div class="user">You: ${userText}</div>`;

  // Append the system's response to the log (with a "system" CSS class)
  // Replace newline characters "\n" with <br> tags for HTML line breaks
  log.innerHTML += `<div class="system">System: ${data.system_output.replace(/\n/g, "<br>")}</div>`;

  // Scroll the log to the bottom so the latest messages are visible
  log.scrollTop = log.scrollHeight;

  // Get the debug state div element
  const stateDiv = document.getElementById("state");

  // Show the state as pretty-printed JSON (2-space indentation)
  stateDiv.textContent = "State:\n" + JSON.stringify(data.state, null, 2);
}

// This function sends a POST request to /api/reset to reset the backend state
async function resetState() {
  // Send a POST request with no body just to trigger reset
  await fetch("/api/reset", { method: "POST" });

  // Clear the message log on the front end
  document.getElementById("log").innerHTML = "";

  // Reset the debug state display text
  document.getElementById("state").textContent = "State: (reset)";
}

// Wait until the HTML document is fully loaded before wiring up event listeners
document.addEventListener("DOMContentLoaded", () => {
  // Get references to the form, input box, and reset button
  const form = document.getElementById("input-form");
  const input = document.getElementById("user-input");
  const resetBtn = document.getElementById("reset-btn");

  // Add a handler for when the form is submitted (when "Send" is clicked or Enter is pressed)
  form.addEventListener("submit", (e) => {
    // Prevent the default form submission behavior (page reload)
    e.preventDefault();

    // Read the user's text from the input box and trim extra spaces
    const text = input.value.trim();

    // If the input is empty, do nothing
    if (!text) return;

    // Call sendInput to send this text to the backend
    sendInput(text);

    // Clear the input box after sending
    input.value = "";
  });

  // Add a handler for when the "Reset" button is clicked
  resetBtn.addEventListener("click", () => {
    // Call resetState to tell the backend to reset and clear the front-end log
    resetState();
  });

  // Optionally, reset the state when the page first loads
  resetState();
});
