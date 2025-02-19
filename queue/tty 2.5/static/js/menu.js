function displayDateTime() {
  const dateTimeElement = document.getElementById("date-time");
  const now = new Date();
  const formattedDate = now.toLocaleDateString();
  const formattedTime = now.toLocaleTimeString();
  dateTimeElement.textContent = `${formattedDate} ${formattedTime}`;
}

setInterval(displayDateTime, 1000);

function getUserRole() {
  return "admin";
}

function configureMenu() {
  const userRole = getUserRole();
  const editorButton = document.querySelector("li[data-menu='editor']");
  const queueButton = document.querySelector("li[data-menu='queue']");

  if (userRole !== "superadmin") {
    editorButton.style.display = "none";
  }

  if (window.location.pathname.includes("tables.html")) {
    queueButton.style.display = "none";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  configureMenu();
  displayDateTime();
});








// Функция для проверки статуса администратора
function checkAdminStatus() {
  fetch('/check_admin_status')
      .then(response => response.json())
      .then(data => {
          // Если администратор занял стол
          if (data.tableAssigned) {
              // Разблокировать кнопку и установить правильную ссылку
              document.getElementById('queue-button').disabled = false;
              document.getElementById('queue-button').setAttribute('href', `/manage_table/${data.tableId}`);
          } else {
              // Если стол не занят, кнопка остаётся неактивной
              document.getElementById('queue-button').disabled = false;
              document.getElementById('queue-button').setAttribute('href', `/choose_table`);
          }
      })
      .catch(error => console.error('Ошибка при проверке статуса:', error));
}

function redirectToTable() {
  window.location.href = document.getElementById('queue-button').getAttribute('href');
}

document.getElementById('queue-button').addEventListener('click', function(event) {
  event.preventDefault();

  checkAdminStatus();

  setTimeout(redirectToTable, 500);
});