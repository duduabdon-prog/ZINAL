// admin.js
async function fetchUsers(){
    const res = await fetch('/api/admin/users');
    if(!res.ok) return;
    const payload = await res.json();
    const tbody = document.querySelector('#usersTable tbody');
    tbody.innerHTML = '';
    payload.users.forEach(u => {
        let exp;
        if (u.access_expires_at) {
            const expDate = new Date(u.access_expires_at);
            if (Date.now() > expDate.getTime()) {
                exp = `<span style="color:red;font-weight:bold;">Expirado</span>`;
            } else {
                exp = expDate.toLocaleString();
            }
        } else {
            exp = 'Vitalício';
        }

        const last = u.last_analysis_started_at ? new Date(u.last_analysis_started_at).toLocaleString() : '-';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${u.id}</td>
            <td>${u.email}</td>
            <td>${u.username}</td>
            <td>${u.is_admin ? 'Sim' : 'Não'}</td>
            <td>${exp}</td>
            <td>${last}</td>
            <td>
              <button onclick="editUser(${u.id})">Editar</button>
              <button onclick="renewAccess(${u.id})">Renovar</button>
              <button onclick="deleteUser(${u.id})">Excluir</button>
            </td>`;
        tbody.appendChild(tr);
    });
}

async function fetchClicks(){
    const res = await fetch('/api/admin/clicks/list');
    if(!res.ok) return;
    const payload = await res.json();
    const tbody = document.querySelector('#clicksTable tbody');
    tbody.innerHTML = '';
    payload.logs.forEach(l => {
        const tr = document.createElement('tr');
        const when = new Date(l.clicked_at).toLocaleString();
        tr.innerHTML = `<td>${l.id}</td><td>${l.username || l.user_id}</td><td>${l.button_name}</td><td>${when}</td>`;
        tbody.appendChild(tr);
    });
}

let clicksChart = null;
async function drawStats(period='daily'){
    const res = await fetch(`/api/admin/clicks/stats?period=${period}`);
    if(!res.ok) return;
    const payload = await res.json();
    const ctx = document.getElementById('clicksChart').getContext('2d');
    if(clicksChart) clicksChart.destroy();
    clicksChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: payload.labels,
            datasets: [
                { label: 'Telegram', data: payload.telegram, backgroundColor: 'rgba(42,139,242,0.8)' },
                { label: 'Compra', data: payload.compra, backgroundColor: 'rgba(255,212,0,0.9)' },
                { label: 'Total', data: payload.total, backgroundColor: 'rgba(180,180,180,0.3)' }
            ]
        },
        options: {
            responsive: true,
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
        }
    });
}

// criar usuário
document.getElementById('createUserForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const body = {
        email: formData.get('email'),
        username: formData.get('username'),
        password: formData.get('password'),
        is_admin: formData.get('is_admin') === 'on'
    };
    const vitalicio = document.getElementById('vitalicio').checked;
    if(!vitalicio){
        const v = document.getElementById('access_expires_at').value;
        if(v) body.access_expires_at = new Date(v).getTime();
    } else {
        body.access_expires_at = null;
    }
    const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const payload = await res.json();
    const msg = document.getElementById('createUserMsg');
    if(res.ok && payload.ok){
        msg.style.color = 'green';
        msg.innerText = 'Usuário criado!';
        form.reset();
        fetchUsers();
    } else {
        msg.style.color = 'red';
        msg.innerText = payload.error || 'Erro';
    }
});

function toggleExp(){
    const chk = document.getElementById('vitalicio');
    const input = document.getElementById('access_expires_at');
    input.disabled = chk.checked;
    if(chk.checked) input.value = '';
}

async function deleteUser(id){
    if(!confirm('Excluir usuário?')) return;
    const res = await fetch(`/api/admin/users/${id}`, { method: 'DELETE' });
    if(res.ok) fetchUsers();
    else alert('Erro ao excluir');
}

async function editUser(id){
    const novoNome = prompt('Novo username (deixe em branco para não alterar):');
    const novoEmail = prompt('Novo email (deixe em branco para não alterar):');
    const novaSenha = prompt('Nova senha (deixe em branco para não alterar):');

    const body = {};
    if(novoNome) body.username = novoNome;
    if(novoEmail) body.email = novoEmail;
    if(novaSenha) body.password = novaSenha;

    const res = await fetch(`/api/admin/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if(res.ok) fetchUsers();
    else alert('Erro ao editar');
}

// nova função para renovar acesso
async function renewAccess(id){
    const novaData = prompt('Digite a nova data de expiração (YYYY-MM-DD HH:MM):');
    if(!novaData) return;
    const timestamp = new Date(novaData).getTime();
    if(isNaN(timestamp)) {
        alert('Data inválida!');
        return;
    }
    const res = await fetch(`/api/admin/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_expires_at: timestamp })
    });
    if(res.ok) {
        alert('Acesso renovado!');
        fetchUsers();
    } else {
        alert('Erro ao renovar acesso');
    }
}

document.getElementById('periodSelect').addEventListener('change', (e) => {
    drawStats(e.target.value);
});

// initial load
fetchUsers();
fetchClicks();
drawStats('daily');
