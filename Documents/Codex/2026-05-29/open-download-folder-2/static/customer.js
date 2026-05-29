const shell = document.querySelector(".customer-shell");
const computerId = shell.dataset.computerId;
const token = shell.dataset.token || "";
const nameEl = document.querySelector("#pc-name");
const topNameEl = document.querySelector("#top-pc-name");
const stateEl = document.querySelector("#session-state");
const timeEl = document.querySelector("#remaining-time");
const topTimeEl = document.querySelector("#top-remaining-time");
const noteEl = document.querySelector("#customer-note");
const meterEl = document.querySelector("#meter-fill");
const blockedEl = document.querySelector("#blocked-screen");
const blockedMessageEl = document.querySelector("#blocked-message");

function formatTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remainingSeconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

async function refresh() {
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const response = await fetch(`/api/computers/${computerId}${query}`);
  const computer = await response.json();
  nameEl.textContent = computer.name || "Customer PC";
  topNameEl.textContent = computer.name || "QOOHI";
  timeEl.textContent = formatTime(computer.remaining_seconds);
  topTimeEl.textContent = formatTime(computer.remaining_seconds);

  if (computer.status === "active") {
    stateEl.textContent = "Session active";
    noteEl.textContent = "Your paid time is running.";
    blockedEl.classList.remove("show");
    meterEl.style.width = `${Math.max(4, Math.min(100, computer.remaining_seconds / (computer.session.minutes * 60) * 100))}%`;
  } else {
    stateEl.textContent = "Locked";
    noteEl.textContent = "Please pay at the counter to start a session.";
    blockedMessageEl.textContent = "Time is finished. Ask the operator to add time.";
    blockedEl.classList.add("show");
    meterEl.style.width = "0%";
  }
}

refresh();
setInterval(refresh, 1000);
