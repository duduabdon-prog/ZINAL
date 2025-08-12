// dashboard.js (final)
// Candlestick via Chart.js + chartjs-chart-financial
// Comporta: simulação 7-20s antes de mostrar a análise, mantém bloqueio de 7 minutos

let candlestickChart = null;
let candleData = [];

// helpers
function pad(n){ return n.toString().padStart(2,'0'); }
function formatTimeFromMs(ms){ const d = new Date(ms); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; }

function gerarCandle(base) {
    const open = +(base + (Math.random() - 0.5) * 0.6).toFixed(2);
    const close = +(open + (Math.random() - 0.5) * 0.8).toFixed(2);
    const high = +Math.max(open, close) + Math.random() * 0.6;
    const low = +Math.min(open, close) - Math.random() * 0.6;
    return { x: new Date(), o: open, h: +high.toFixed(2), l: +low.toFixed(2), c: close };
}

function initCandles() {
    const ctx = document.getElementById('candlestickChart').getContext('2d');

    // initial candles
    let price = 100 + Math.random() * 10;
    for(let i = 0; i < 50; i++){
        candleData.push(gerarCandle(price));
        price = candleData[candleData.length - 1].c;
    }

    candlestickChart = new Chart(ctx, {
        type: 'candlestick',
        data: {
            datasets: [{
                label: 'Preço (simulado)',
                data: candleData,
                color: {
                    up: '#00FF90',
                    down: '#FF4E4E',
                    unchanged: '#999999'
                }
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#9AA0A6' } },
                y: { ticks: { color: '#9AA0A6' } }
            },
            maintainAspectRatio: false,
            responsive: true
        }
    });

    // push new candle every 1s (simulated)
    window.candleInterval = setInterval(() => {
        const last = candleData[candleData.length - 1].c || 100;
        const next = gerarCandle(last);
        candleData.push(next);
        if(candleData.length > 80) candleData.shift();
        candlestickChart.update();
    }, 1000);
}

function stopCandles() {
    if(window.candleInterval) clearInterval(window.candleInterval);
    window.candleInterval = null;
}

function startCandlesAgain(){
    if(!window.candleInterval){
        if(candlestickChart){
            window.candleInterval = setInterval(() => {
                const last = candleData[candleData.length - 1].c || 100;
                const next = gerarCandle(last);
                candleData.push(next);
                if(candleData.length > 80) candleData.shift();
                candlestickChart.update();
            }, 1000);
        } else {
            initCandles();
        }
    }
}

// registrar cliques (telegram / compra)
function registrarClique(botao, linkFinal){
    fetch('/api/registrar-clique', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ button_name: botao })
    }).then(r => r.json()).then(j => {
        if(j.success){
            window.open(linkFinal, '_blank');
        } else {
            alert('Erro ao registrar clique');
        }
    }).catch(e => { console.error(e); alert('Erro'); });
}

// Inicia análise: chama API, espera 7-20s (simulado), mostra análise, bloqueia por 7 minutos
async function startAnalysis(){
    const btn = document.getElementById('startAnalysisBtn');
    btn.disabled = true;
    btn.innerText = 'ANALISANDO...';
    document.getElementById('status-msg').innerText = 'I.A ANALISANDO MERCADO...';

    try{
        const res = await fetch('/api/start-analysis', { method: 'POST' });

        // blocked pela API
        if(res.status === 429){
            const payload = await res.json();
            if(payload.blocked_until){
                startCountdown(payload.blocked_until);
                document.getElementById('status-msg').innerText = 'Bloqueado. Aguarde...';
                btn.innerText = 'BLOQUEADO';
            }
            return;
        }
        if(!res.ok){
            const j = await res.json();
            alert(j.error || 'Erro');
            btn.disabled = false;
            btn.innerText = 'INICIAR ANÁLISE';
            document.getElementById('status-msg').innerText = '';
            return;
        }

        const data = await res.json();
        const blockedUntil = data.blocked_until;

        // AQUI: simulação de "análise" por 7..20s
        const delayMs = 7000 + Math.floor(Math.random() * 13001); // 7000..20000
        // Mantém o gráfico rodando enquanto simula (efeito visual)
        await new Promise(r => setTimeout(r, delayMs));

        // Após espera: esconder gráfico, mostrar análise
        stopCandles();
        document.getElementById('chartContainer').style.display = 'none';
        document.getElementById('analysisBox').style.display = 'block';

        // monta HTML da análise (link integrado)
        const analysisHtml = `
<div style="font-weight:800;color:var(--logo-yellow);font-size:18px;margin-bottom:8px;">⚠️ ${data.titulo} ⚠️</div>
<div style="font-size:16px;">
💵 Moeda = <strong>${data.moeda}</strong><br>
⏰ Expiração = ${data.expiracao}<br>
🛎 Entrada = ${data.entrada}<br>
${data.direcao}<br><br>
♾️ 1ª Proteção🛡️ - ${data.protecao1}<br>
♾️ 2ª Proteção🛡️ - ${data.protecao2}<br><br>
👉🏼 Até 2 reentradas se necessário<br><br>
➡️ <a href="https://www.homebroker.com/ref/feT3lSod/" target="_blank" rel="noopener noreferrer">Cadastre-se na corretora</a>
</div>
        `;
        document.getElementById('analysisContent').innerHTML = analysisHtml;

        // inicia contagem regressiva com base em blockedUntil retornado pelo servidor
        startCountdown(blockedUntil);

    }catch(err){
        console.error(err);
        alert('Erro iniciando análise');
        document.getElementById('startAnalysisBtn').disabled = false;
        document.getElementById('startAnalysisBtn').innerText = 'INICIAR ANÁLISE';
        document.getElementById('status-msg').innerText = '';
    }
}

let countdownInterval = null;
function startCountdown(blockedUntilMs){
    if(countdownInterval) clearInterval(countdownInterval);
    const display = document.getElementById('analysisCountdown');

    function tick(){
        const now = Date.now();
        const rem = blockedUntilMs - now;
        if(rem <= 0){
            // finaliza: volta ao gráfico, habilita botão
            document.getElementById('analysisBox').style.display = 'none';
            document.getElementById('chartContainer').style.display = 'block';
            document.getElementById('startAnalysisBtn').disabled = false;
            document.getElementById('startAnalysisBtn').innerText = 'INICIAR ANÁLISE';
            document.getElementById('status-msg').innerText = 'Clique no botão para iniciar a análise';
            if(countdownInterval) clearInterval(countdownInterval);
            startCandlesAgain();
            display.innerText = '';
            return;
        }
        const mm = Math.floor(rem / 60000);
        const ss = Math.floor((rem % 60000) / 1000);
        display.innerText = `Aguarde a liberação — tempo restante: ${pad(mm)}:${pad(ss)}`;
    }
    tick();
    countdownInterval = setInterval(tick, 1000);
}

// on load: inicia candles e sincroniza estado do usuário
window.addEventListener('load', async () => {
    initCandles();

    try{
        const res = await fetch('/api/user/me');
        if(res.ok){
            const payload = await res.json();
            if(payload && payload.user && payload.user.blocked_until){
                startCountdown(payload.user.blocked_until);
                document.getElementById('startAnalysisBtn').disabled = true;
                document.getElementById('startAnalysisBtn').innerText = 'BLOQUEADO';
                document.getElementById('status-msg').innerText = 'Você está em período de bloqueio.';
            }
        }
    }catch(e){ console.warn('sync error', e); }
});
