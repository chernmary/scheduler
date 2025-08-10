const API_BASE = '/employees';

const tabMain = document.getElementById('tab-main');
const tabHelpers = document.getElementById('tab-helpers');
const tbodyMain = document.getElementById('employees-tbody');
const tbodyHelpers = document.getElementById('helpers-tbody');
const modal = document.getElementById('emp-modal');
const confirmModal = document.getElementById('confirm-modal');
const empForm = document.getElementById('emp-form');

let currentRole = 'main'; // main | helper

// ===================== Загрузка сотрудников =====================
async function loadEmployees(role) {
    try {
        const res = await fetch(`${API_BASE}?is_helper=${role === 'helper' ? 'true' : 'false'}`);
        if (!res.ok) throw new Error();
        const data = await res.json();

        const tbody = role === 'helper' ? tbodyHelpers : tbodyMain;
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
                    <button class="btn" onclick="editEmployee(${emp.id})">✏️</button>
                    <button class="btn danger" onclick="deleteEmployee(${emp.id})">🗑️</button>
                    ${role === 'main'
                        ? `<button class="btn" onclick="moveEmployee(${emp.id}, 'to-helper')">➡️ Хелпер</button>`
                        : `<button class="btn" onclick="moveEmployee(${emp.id}, 'to-main')">⬅️ Основной</button>`}
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        const tbody = role === 'helper' ? tbodyHelpers : tbodyMain;
        tbody.innerHTML = `<tr><td colspan="3">Ошибка загрузки</td></tr>`;
    }
}

function refreshAll() {
    loadEmployees('main');
    loadEmployees('helper');
}

// ===================== Добавление / редактирование =====================
document.getElementById('btn-add').addEventListener('click', () => {
    empForm.reset();
    empForm.id.value = '';
    document.getElementById('modal-title').textContent = 'Новый сотрудник';
    modal.showModal();
});

empForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(empForm);
    const id = fd.get('id');
    const payload = {
        full_name: fd.get('full_name'),
        is_helper: currentRole === 'helper',
        on_sick_leave: fd.get('on_sick_leave') === 'on'
    };

    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_BASE}/${id}` : `${API_BASE}`;

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
});

// ===================== Редактирование =====================
async function editEmployee(id) {
    const res = await fetch(`${API_BASE}/${id}`);
    if (!res.ok) return alert('Ошибка загрузки данных');
    const emp = await res.json();

    empForm.full_name.value = emp.full_name;
    empForm.on_sick_leave.checked = emp.on_sick_leave;
    empForm.id.value = emp.id;
    document.getElementById('modal-title').textContent = 'Редактировать сотрудника';
    modal.showModal();
}

// ===================== Удаление =====================
async function deleteEmployee(id) {
    if (!confirm('Удалить сотрудника?')) return;
    const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
    if (res.ok) {
        refreshAll();
    } else {
        alert('Ошибка удаления');
    }
}

// ===================== Перемещение между ролями =====================
async function moveEmployee(id, action) {
    const res = await fetch(`${API_BASE}/${id}`);
    if (!res.ok) return alert('Ошибка загрузки данных');
    const emp = await res.json();

    emp.is_helper = (action === 'to-helper');

    const saveRes = await fetch(`${API_BASE}/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emp)
    });

    if (saveRes.ok) {
        refreshAll();
    } else {
        alert('Ошибка перемещения');
    }
}

// ===================== Переключение вкладок =====================
tabMain.addEventListener('click', () => {
    currentRole = 'main';
    tabMain.classList.add('active');
    tabHelpers.classList.remove('active');
    document.getElementById('panel-main').classList.remove('hidden');
    document.getElementById('panel-helpers').classList.add('hidden');
});
tabHelpers.addEventListener('click', () => {
    currentRole = 'helper';
    tabHelpers.classList.add('active');
    tabMain.classList.remove('active');
    document.getElementById('panel-helpers').classList.remove('hidden');
    document.getElementById('panel-main').classList.add('hidden');
});

// ===================== Старт =====================
refreshAll();
