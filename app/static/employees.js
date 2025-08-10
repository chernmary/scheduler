// ==== БАЗА API (JSON) ====
const API_BASE = '/employees'; // было '/admin/employees'

// ==== ЭЛЕМЕНТЫ ====
const tabMain = document.getElementById('tab-main');
const tabHelpers = document.getElementById('tab-helpers');
const tbodyMain = document.getElementById('employees-tbody');
const tbodyHelpers = document.getElementById('helpers-tbody');

const modal = document.getElementById('emp-modal');
const empForm = document.getElementById('emp-form');
const btnCancel = document.getElementById('btn-cancel');

let currentRole = 'main'; // 'main' | 'helper'

// ===================== Утилиты =====================
async function jsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
function renderError(tbody) {
  tbody.innerHTML = `<tr><td colspan="3">Ошибка загрузки</td></tr>`;
}

// ===================== Загрузка сотрудников =====================
async function loadEmployees(role) {
  const tbody = role === 'helper' ? tbodyHelpers : tbodyMain;

  try {
    const data = await jsonFetch(`${API_BASE}?is_helper=${role === 'helper' ? 'true' : 'false'}`);
    tbody.innerHTML = '';

    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="3">Нет данных</td></tr>`;
      return;
    }

    data.forEach(emp => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${emp.full_name}</td>
        <td>${emp.on_sick_leave ? 'Да' : 'Нет'}</td>
        <td class="actions-col">
          <button class="btn" data-edit="${emp.id}">✏️</button>
          <button class="btn danger" data-del="${emp.id}">🗑️</button>
          ${
            role === 'main'
              ? `<button class="btn" data-move="${emp.id}" data-action="to-helper">➡️ Хелпер</button>`
              : `<button class="btn" data-move="${emp.id}" data-action="to-main">⬅️ Основной</button>`
          }
        </td>
      `;
      tbody.appendChild(tr);
    });

  } catch (e) {
    renderError(tbody);
  }
}

function refreshAll() {
  loadEmployees('main');
  loadEmployees('helper');
}

// Делегирование кликов по кнопкам в таблицах
[tbodyMain, tbodyHelpers].forEach(tbody => {
  tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;

    // Удаление
    if (btn.dataset.del) {
      const id = btn.dataset.del;
      if (!confirm('Удалить сотрудника?')) return;
      const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
      if (res.ok) refreshAll(); else alert('Ошибка удаления');
      return;
    }

    // Редактирование
    if (btn.dataset.edit) {
      const id = btn.dataset.edit;
      try {
        const emp = await jsonFetch(`${API_BASE}/${id}`); // нужен GET /employees/{id}
        empForm.reset();
        empForm.full_name.value = emp.full_name ?? '';
        empForm.on_sick_leave.checked = !!emp.on_sick_leave;
        empForm.id.value = emp.id;
        document.getElementById('modal-title').textContent = 'Редактировать сотрудника';
        modal.showModal();
      } catch {
        alert('Ошибка загрузки данных сотрудника');
      }
      return;
    }

    // Перемещение между ролями
    if (btn.dataset.move) {
      const id = btn.dataset.move;
      const action = btn.dataset.action; // 'to-helper' | 'to-main'
      try {
        // Получаем текущие поля сотрудника, меняем is_helper и сохраняем
        const emp = await jsonFetch(`${API_BASE}/${id}`); // нужен GET /employees/{id}
        const updated = {
          full_name: emp.full_name,
          on_sick_leave: !!emp.on_sick_leave,
          is_helper: action === 'to-helper'
        };
        const res = await fetch(`${API_BASE}/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updated)
        });
        if (res.ok) refreshAll(); else alert('Ошибка перемещения');
      } catch {
        alert('Ошибка перемещения');
      }
      return;
    }
  });
});

// ===================== Добавление / сохранение =====================
document.getElementById('btn-add').addEventListener('click', () => {
  empForm.reset();
  empForm.id.value = '';
  document.getElementById('modal-title').textContent = 'Новый сотрудник';
  modal.showModal();
});

btnCancel.addEventListener('click', () => {
  modal.close();
});

empForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  // встроенная валидация формы
  if (!empForm.reportValidity()) return;

  const fd = new FormData(empForm);
  const id = fd.get('id');
  const payload = {
    full_name: fd.get('full_name'),
    is_helper: currentRole === 'helper',      // новая запись попадает в текущую вкладку
    on_sick_leave: fd.get('on_sick_leave') === 'on'
  };

  const method = id ? 'PUT' : 'POST';
  const url = id ? `${API_BASE}/${id}` : `${API_BASE}`;

  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      modal.close();
      refreshAll();
    } else {
      alert('Ошибка сохранения');
    }
  } catch {
    alert('Ошибка сохранения');
  }
});

// ===================== Переключение вкладок =====================
tabMain.addEventListener('click', () => {
  currentRole = 'main';
  tabMain.classList.add('active');
  tabHelpers.classList.remove('active');
  document.getElementById('panel-main').classList.remove('hidden');
  document.getElementById('panel-helpers').classList.add('hidden');
  loadEmployees('main');
});

tabHelpers.addEventListener('click', () => {
  currentRole = 'helper';
  tabHelpers.classList.add('active');
  tabMain.classList.remove('active');
  document.getElementById('panel-helpers').classList.remove('hidden');
  document.getElementById('panel-main').classList.add('hidden');
  loadEmployees('helper');
});

// ===================== Старт =====================
refreshAll();
