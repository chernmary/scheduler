(function(){
  const tabMain = document.getElementById('tab-main');
  const tabHelpers = document.getElementById('tab-helpers');
  const panelMain = document.getElementById('panel-main');
  const panelHelpers = document.getElementById('panel-helpers');
  const tbodyMain = document.getElementById('employees-tbody');
  const tbodyHelpers = document.getElementById('helpers-tbody');
  const btnAdd = document.getElementById('btn-add');

  const modal = document.getElementById('emp-modal');
  const form = document.getElementById('emp-form');
  const modalTitle = document.getElementById('modal-title');
  const btnCancel = document.getElementById('btn-cancel');

  const confirmModal = document.getElementById('confirm-modal');
  const confirmText = document.getElementById('confirm-text');
  const confirmOk = document.getElementById('confirm-ok');
  const confirmCancel = document.getElementById('confirm-cancel');

  function setActive(tab){
    if(tab === 'main'){
      tabMain.classList.add('active');
      tabHelpers.classList.remove('active');
      panelMain.classList.remove('hidden');
      panelHelpers.classList.add('hidden');
    }else{
      tabHelpers.classList.add('active');
      tabMain.classList.remove('active');
      panelHelpers.classList.remove('hidden');
      panelMain.classList.add('hidden');
    }
  }

  function escapeHtml(str){
    if(str == null) return '';
    return String(str)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;')
      .replace(/'/g,'&#039;');
  }

  function sickBadge(val){
    return val ? 'Да' : 'Нет';
  }

  function actionButtons(item, role){
    if(role === 'main'){
      return `
        <div class="row-actions">
          <button class="btn" data-act="edit" data-id="${item.id}">Редактировать</button>
          <button class="btn" data-act="to-helper" data-id="${item.id}">В хелперы</button>
          <button class="btn danger" data-act="delete" data-id="${item.id}">Удалить</button>
        </div>
      `;
    }else{
      return `
        <div class="row-actions">
          <button class="btn" data-act="edit" data-id="${item.id}">Редактировать</button>
          <button class="btn" data-act="to-main" data-id="${item.id}">В основные</button>
          <button class="btn danger" data-act="delete" data-id="${item.id}">Удалить</button>
        </div>
      `;
    }
  }

  function renderRows(tbody, items, role){
    tbody.innerHTML = items.map(it => `
      <tr data-id="${it.id}">
        <td>${escapeHtml(it.full_name)}</td>
        <td>${sickBadge(it.on_sick_leave)}</td>
        <td class="actions-col">${actionButtons(it, role)}</td>
      </tr>
    `).join('');
  }

  async function load(role){
    try{
      const res = await fetch(`/employees?is_helper=${role === 'helper' ? 'true' : 'false'}`);
      if(!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if(role === 'main'){
        renderRows(tbodyMain, data, 'main');
      }else{
        renderRows(tbodyHelpers, data, 'helper');
      }
    }catch(e){
      console.error('Не удалось загрузить сотрудников:', e);
      const msg = [{ id:0, full_name: 'Ошибка загрузки', on_sick_leave: false }];
      if(role === 'main') renderRows(tbodyMain, msg, 'main'); else renderRows(tbodyHelpers, msg, 'helper');
    }
  }

  function openCreate(){
    modalTitle.textContent = 'Новый сотрудник';
    form.reset();
    form.elements['id'].value = '';
    form.elements['on_sick_leave'].checked = false;
    modal.showModal();
  }

  function openEdit(row, role){
    modalTitle.textContent = 'Редактирование';
    form.reset();
    form.elements['id'].value = row.id;
    form.elements['full_name'].value = row.full_name || '';
    form.elements['on_sick_leave'].checked = !!row.on_sick_leave;
    modal.showModal();
  }

  async function submitForm(e){
    e.preventDefault();
    const fd = new FormData(form);
    const id = fd.get('id') || '';
    const role = tabMain.classList.contains('active') ? 'main' : 'helper';

    const payload = {
      full_name: fd.get('full_name'),
      is_helper: role === 'helper',
      on_sick_leave: fd.get('on_sick_leave') === 'on'
    };

    const opts = {
      method: id ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    };
    const url = id ? `/employees/${id}` : `/employees`;
    const res = await fetch(url, opts);
    if(!res.ok){
      alert('Ошибка сохранения: ' + res.status);
      return;
    }
    modal.close();
    refreshAll();
  }

  function confirm(text){
    return new Promise(resolve => {
      confirmText.textContent = text;
      confirmModal.showModal();
      function cleanup(ok){
        confirmOk.removeEventListener('click', okH);
        confirmCancel.removeEventListener('click', cancelH);
        confirmModal.close();
        resolve(ok);
      }
      function okH(){ cleanup(true); }
      function cancelH(){ cleanup(false); }
      confirmOk.addEventListener('click', okH, { once:true });
      confirmCancel.addEventListener('click', cancelH, { once:true });
    });
  }

  async function onTableClick(e, role){
    const btn = e.target.closest('button[data-act]');
    if(!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    const rowEl = btn.closest('tr');
    const row = {
      id,
      full_name: rowEl.children[0].textContent,
      on_sick_leave: rowEl.children[1].textContent.trim() === 'Да'
    };

    if(act === 'edit'){
      openEdit(row, role);
      return;
    }
    if(act === 'to-helper'){
      if(await confirm('Перевести в хелперы?')){
        await fetch(`/employees/${id}/to-helper`, { method:'POST' });
        refreshAll();
      }
      return;
    }
    if(act === 'to-main'){
      if(await confirm('Перевести в основные?')){
        await fetch(`/helpers/${id}/to-main`, { method:'POST' });
        refreshAll();
      }
      return;
    }
    if(act === 'delete'){
      if(await confirm('Удалить сотрудника безвозвратно?')){
        const res = await fetch(`/employees/${id}`, { method:'DELETE' });
        if(!res.ok) alert('Ошибка удаления: ' + res.status);
        refreshAll();
      }
      return;
    }
  }

  function refreshAll(){ load('main'); load('helper'); }

  tabMain.addEventListener('click', () => { setActive('main'); load('main'); });
  tabHelpers.addEventListener('click', () => { setActive('helper'); load('helper'); });
  btnAdd.addEventListener('click', openCreate);
  btnCancel.addEventListener('click', () => modal.close());
  form.addEventListener('submit', submitForm);

  tbodyMain.addEventListener('click', (e) => onTableClick(e, 'main'));
  tbodyHelpers.addEventListener('click', (e) => onTableClick(e, 'helper'));

  // Старт
  setActive('main'); load('main'); load('helper');
})();
