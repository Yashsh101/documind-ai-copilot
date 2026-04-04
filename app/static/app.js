const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const messages = document.querySelector("#messages");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerText = text;
  messages.appendChild(div);
}

async function sendMessage(text) {
  addMessage("user", text);

  const bot = document.createElement("div");
  bot.className = "message assistant";
  bot.innerText = "Thinking...";
  messages.appendChild(bot);

  try {
    const res = await fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ question: text })
    });

    const data = await res.text();
    bot.innerText = data;

  } catch (e) {
    bot.innerText = "⚠️ Error getting response";
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const text = input.value.trim();
  if (!text) return;

  input.value = "";

  await sendMessage(text);
});