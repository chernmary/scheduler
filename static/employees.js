(function(){
  const tabMain = document.getElementById('tab-main');
  const tabHelpers = document.getElementById('tab-helpers');
  const panelMain = document.getElementById('panel-main');
  const panelHelpers = document.getElementById('panel-helpers');
  const tbodyMain = document.getElementById('employees-tbody');
  const tbodyHelpers = document.getElementById('helpers-tbody');

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

  function fmtDate(dateStr){
    if(!dateStr) return '';
    const d = new Date(dateStr);
    if(isNaN(d)) return dateStr;
    return d.toLocaleDateString('ru-RU', { year:'numeric', month:'2-digit', day:'2-digit' });
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

  function renderRows(tbody, items){
    tbody.innerHTML = items.map(it => `
      <tr>
        <td>${escapeHtml(it.full_name)}</td>
        <td>${escapeHtml(it.phone || '')}</td>
        <td>${escapeHtml(it.telegram || '')}</td>
        <td>${fmtDate(it.birth_date)}</td>
        <td>${fmtDate(it.medbook_expiry)}</td>
        <td>${escapeHtml(it.notes || '')}</td>
      </tr>
    `).join('');
  }

  async function load(role){
    try{
      const res = await fetch(`/employees?role=${role}`);
      if(!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if(role === 'main'){
        renderRows(tbodyMain, data);
      }else{
        renderRows(tbodyHelpers, data);
      }
    }catch(e){
      console.error('Не удалось загрузить сотрудников:', e);
      const msg = [{ full_name: 'Ошибка загрузки', phone:'', telegram:'', birth_date:'', medbook_expiry:'', notes:'' }];
      if(role === 'main') renderRows(tbodyMain, msg); else renderRows(tbodyHelpers, msg);
    }
  }

  tabMain.addEventListener('click', () => { setActive('main'); load('main'); });
  tabHelpers.addEventListener('click', () => { setActive('helper'); load('helper'); });

  // Стартуем с "Основных"
  setActive('main');
  load('main');
})();
