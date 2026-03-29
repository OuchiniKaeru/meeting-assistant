'use strict';

// Socket.IO接続
const socket = io();

// DOM要素の取得
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const statusDiv = document.getElementById('status');
const currentTextDiv = document.getElementById('currentText');
const historyDiv = document.getElementById('history');
const summaryContentDiv = document.getElementById('summaryContent');
const qaContentDiv = document.getElementById('qaContent');

// Markdownパーサー設定
marked.setOptions({
    breaks: true,
    gfm: true
});

// イベントリスナー
startBtn.addEventListener('click', () => {
    if (socket.connected) {
        socket.emit('start_parallel_processing');
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusDiv.textContent = '認識開始要求を送信しました...';
        statusDiv.className = 'status';
    } else {
        alert('サーバーに接続されていません');
    }
});

stopBtn.addEventListener('click', () => {
    if (socket.connected) {
        socket.emit('stop_parallel_processing');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusDiv.textContent = '停止 yêu求を送信しました...';
        statusDiv.className = 'status';
    } else {
        alert('サーバーに接続されていません');
    }
});

clearBtn.addEventListener('click', () => {
    socket.emit('clear_history');
});

// Socket Events
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('status', (data) => {
    console.log('Status received:', data);
    updateStatusUI(data.is_running);
});

socket.on('parallel_started', (data) => {
    updateStatusUI(true, data.message);
});

socket.on('parallel_stopped', (data) => {
    updateStatusUI(false, data.message);
});

socket.on('error', (data) => {
    alert('エラー: ' + data.message);
    updateStatusUI(false, "エラーによって停止しました");
});

socket.on('gemini_recognizing', (data) => {
    currentTextDiv.innerHTML = `<em>${data.text}</em>`;
});

socket.on('gemini_recognized', (data) => {
    currentTextDiv.innerHTML = '';
    const itemInfo = document.createElement('div');
    itemInfo.className = 'history-item';
    itemInfo.innerHTML = `
        <div class="time">${data.timestamp}</div>
        <div class="text">${data.text}</div>
    `;
    historyDiv.prepend(itemInfo);
});

socket.on('auto_summary_generated', (data) => {
    console.log('Summary generated:', data);
    summaryContentDiv.innerHTML = marked.parse(data.summary);
});

socket.on('summary_generated', (data) => {
    console.log('Manual summary generated:', data);
    summaryContentDiv.innerHTML = marked.parse(data.summary);
});

socket.on('qa_generated', (data) => {
    console.log('QA generated:', data);
    if (!data.questions || data.questions.length === 0) {
        qaContentDiv.innerHTML = '<div>質問が含まれていません。</div>';
        return;
    }
    
    let html = '';
    data.questions.forEach((q, i) => {
        html += `<div class="qa-item">
            <div class="qa-q">Q${i+1}: ${q.question}</div>`;
        if (q.answers && q.answers.length > 0) {
            q.answers.forEach((ans, j) => {
                if (ans.japanese) {
                    html += `<div class="qa-a">A${j+1}: ${ans.japanese}</div>`;
                }
                if (ans.english && ans.english !== ans.japanese) {
                    html += `<div class="qa-a-en">Eng: ${ans.english}</div>`;
                }
            });
        }
        html += `</div>`;
    });
    qaContentDiv.innerHTML = html;
});

socket.on('history_cleared', (data) => {
    historyDiv.innerHTML = '';
    currentTextDiv.innerHTML = '履歴がクリアされました。';
    summaryContentDiv.innerHTML = '音声が一定量たまると自動的に要約が生成されます。';
    qaContentDiv.innerHTML = '要約内に質問事項が含まれている場合、自動的に回答例が生成されます。';
    console.log(data.message);
});

function updateStatusUI(isRunning, msg) {
    if (isRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusDiv.textContent = msg || '🎙️ 認識中...';
        statusDiv.className = 'status running';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusDiv.textContent = msg || '停止中';
        statusDiv.className = 'status';
    }
}
