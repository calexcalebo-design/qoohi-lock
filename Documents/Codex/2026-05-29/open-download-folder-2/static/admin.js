const grid = document.querySelector("#computer-grid");
const template = document.querySelector("#computer-card-template");
const activeCount = document.querySelector("#active-count");
const lockedCount = document.querySelector("#locked-count");
const cashTotal = document.querySelector("#cash-total");
const emptyState = document.querySelector("#empty-state");
const cards = new Map();

function formatTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60);
  const remainingSeconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

async function postForm(url, data) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(data),
  });
  if (!response.ok) {
    alert("Action failed. Log in again with the admin PIN, then retry.");
    return;
  }
  await loadComputers();
}

function statusText(computer) {
  return computer.status === "active" ? "Paid session running" :
    computer.status === "expired" ? "Time expired" : "Locked";
}

function meterWidth(computer) {
  if (!computer.session || computer.status !== "active") {
    return "0%";
  }
  return `${Math.max(4, Math.min(100, computer.remaining_seconds / (computer.session.minutes * 60) * 100))}%`;
}

function createComputerCard(computer) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.dataset.computerId = computer.id;

  const settingsForm = node.querySelector("[data-settings-form]");
  settingsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    postForm(`/api/computers/${computer.id}/settings`, new FormData(settingsForm));
  });

  const form = node.querySelector("[data-start-form]");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    postForm(`/api/computers/${computer.id}/start`, new FormData(form));
  });

  node.querySelectorAll("[data-add-time]").forEach((button) => {
    button.addEventListener("click", () => {
      postForm(`/api/computers/${computer.id}/add-time`, { plan_id: button.value });
    });
  });

  node.querySelector("[data-stop]").addEventListener("click", () => {
    postForm(`/api/computers/${computer.id}/stop`, {});
  });

  const link = node.querySelector("[data-link]");
  link.href = computer.customer_url;
  updateComputerCard(node, computer, true);
  return node;
}

function updateComputerCard(node, computer, firstRender = false) {
  node.classList.remove("active", "expired", "locked");
  node.classList.add(computer.status);
  node.querySelector("[data-name]").textContent = computer.name;
  node.querySelector("[data-status]").textContent = statusText(computer);
  node.querySelector("[data-time]").textContent = formatTime(computer.remaining_seconds);
  node.querySelector("[data-meter]").style.width = meterWidth(computer);

  const settingsForm = node.querySelector("[data-settings-form]");
  if (firstRender || !settingsForm.matches(":focus-within")) {
    settingsForm.elements.name.value = computer.name;
    settingsForm.elements.ip_address.value = computer.ip_address || "";
  }

  const link = node.querySelector("[data-link]");
  link.href = computer.customer_url;
  node.querySelector("[data-agent]").textContent = computer.ip_address
    ? `Agent target ${computer.ip_address}: run customer_agent.py for real device lock.`
    : "Add this PC's IP address, then run customer_agent.py on that PC for real locking.";
}

async function loadComputers() {
  const response = await fetch("/api/computers");
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  emptyState.hidden = data.computers.length > 0;
  const seen = new Set();
  data.computers.forEach((computer) => {
    seen.add(String(computer.id));
    let node = cards.get(String(computer.id));
    if (!node) {
      node = createComputerCard(computer);
      cards.set(String(computer.id), node);
      grid.appendChild(node);
    } else {
      updateComputerCard(node, computer);
    }
  });
  cards.forEach((node, id) => {
    if (!seen.has(id)) {
      node.remove();
      cards.delete(id);
    }
  });
  const active = data.computers.filter((computer) => computer.status === "active");
  activeCount.textContent = active.length;
  lockedCount.textContent = data.computers.length - active.length;
  cashTotal.textContent = active.reduce((sum, computer) => sum + (computer.session?.amount_ksh || 0), 0);
}

document.querySelector("[data-add-computer]").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  await postForm("/api/computers", new FormData(form));
  form.reset();
});

loadComputers();
setInterval(loadComputers, 1000);
