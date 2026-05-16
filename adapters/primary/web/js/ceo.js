/**
 * ceo.js — Lógica de la vista CEO: consulta RAG + briefing diario + TTS.
 *
 * Endpoints:
 *   POST /api/v1/ceo/query      { question } → { answer, confidence, sources }
 *   GET  /api/v1/ceo/summary    → { summary, checkins_count, period }
 *   POST /api/v1/speech/transcribe  multipart audio → { transcript, confidence }
 *   POST /api/v1/speech/synthesize  { text } → audio/mpeg
 */

'use strict';

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const queryInput        = document.getElementById('query-input');
const btnVoice          = document.getElementById('btn-voice');
const btnQuery          = document.getElementById('btn-query');
const btnSummary        = document.getElementById('btn-summary');
const statusLabel       = document.getElementById('status-label');
const loadingSpinner    = document.getElementById('loading-spinner');

const answerSection     = document.getElementById('answer-section');
const answerText        = document.getElementById('answer-text');
const confidenceBadge   = document.getElementById('confidence-badge');
const answerMeta        = document.getElementById('answer-meta');
const btnReplayAnswer   = document.getElementById('btn-replay-answer');
const sourcesSummaryEl  = document.getElementById('sources-summary');
const sourcesListEl     = document.getElementById('sources-list');
const sourcesSection    = document.getElementById('sources-section');

const summarySection    = document.getElementById('summary-section');
const summaryText       = document.getElementById('summary-text');
const summaryMeta       = document.getElementById('summary-meta');

const toastEl           = document.getElementById('toast');

// ─── State ────────────────────────────────────────────────────────────────────
let mediaRecorder  = null;
let audioChunks    = [];
let isRecording    = false;
let isLoading      = false;
let lastAnswerBlob = null;  // cached TTS for replay

// ─── Utility: toast ───────────────────────────────────────────────────────────
let toastTimer = null;

function showToast(message, durationMs = 4000) {
  toastEl.textContent = message;
  toastEl.classList.add('visible');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.classList.remove('visible');
  }, durationMs);
}

// ─── Utility: loading state ────────────────────────────────────────────────────
function setLoading(busy, statusText = '') {
  isLoading = busy;
  btnQuery.disabled   = busy;
  btnSummary.disabled = busy;
  btnVoice.disabled   = busy;
  loadingSpinner.style.display = busy ? 'inline-block' : 'none';
  statusLabel.textContent = statusText;
  statusLabel.className   = 'status-label' + (busy ? ' processing' : '');
}

// ─── Confidence badge ─────────────────────────────────────────────────────────
const CONFIDENCE_LABELS = {
  alta:       { text: 'Alta confianza',    cls: 'badge-success' },
  media:      { text: 'Confianza media',   cls: 'badge-warning' },
  baja:       { text: 'Baja confianza',    cls: 'badge-danger'  },
  sin_datos:  { text: 'Sin datos',         cls: 'badge-muted'   },
};

function renderConfidenceBadge(confidence) {
  const cfg = CONFIDENCE_LABELS[confidence] || CONFIDENCE_LABELS['sin_datos'];
  confidenceBadge.textContent = cfg.text;
  confidenceBadge.className   = `badge ${cfg.cls}`;
  confidenceBadge.setAttribute('aria-label', `Nivel de confianza: ${cfg.text}`);
}

// ─── Sources list ─────────────────────────────────────────────────────────────
function renderSources(sources) {
  sourcesListEl.innerHTML = '';
  if (!sources || sources.length === 0) {
    sourcesSection.style.display = 'none';
    return;
  }

  sourcesSection.style.display = 'block';
  sourcesSummaryEl.textContent = `Fuentes (${sources.length})`;

  sources.forEach((src) => {
    const item = document.createElement('div');
    item.className = 'source-item';
    item.innerHTML = `
      <div class="source-meta">
        <span class="source-employee">${escapeHtml(src.employee_name)}</span>
        <span class="source-date">${escapeHtml(src.date)}</span>
      </div>
      <p class="source-excerpt">"${escapeHtml(src.excerpt)}"</p>
    `;
    sourcesListEl.appendChild(item);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ─── TTS playback ─────────────────────────────────────────────────────────────
async function playTTS(text) {
  try {
    statusLabel.textContent = 'Sintetizando respuesta...';
    statusLabel.className   = 'status-label playing';
    const res = await fetch('/api/v1/speech/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      console.warn('TTS error:', res.status);
      statusLabel.textContent = '';
      return;
    }
    lastAnswerBlob = await res.blob();
    const audioUrl = URL.createObjectURL(lastAnswerBlob);
    const audio    = new Audio(audioUrl);
    audio.onended = () => {
      statusLabel.textContent = '';
      URL.revokeObjectURL(audioUrl);
    };
    audio.onerror = () => {
      statusLabel.textContent = '';
      URL.revokeObjectURL(audioUrl);
    };
    await audio.play();
  } catch (err) {
    console.warn('TTS playback error (non-fatal):', err);
    statusLabel.textContent = '';
  }
}

// ─── Replay answer ────────────────────────────────────────────────────────────
btnReplayAnswer.addEventListener('click', async () => {
  if (!lastAnswerBlob) return;
  try {
    const audioUrl = URL.createObjectURL(lastAnswerBlob);
    const audio    = new Audio(audioUrl);
    audio.onended  = () => URL.revokeObjectURL(audioUrl);
    await audio.play();
  } catch (err) {
    showToast('Error al reproducir audio.');
  }
});

// ─── CEO Query ────────────────────────────────────────────────────────────────
async function submitQuery() {
  const question = queryInput.value.trim();
  if (!question) {
    showToast('Por favor escribe o habla tu pregunta.');
    queryInput.focus();
    return;
  }
  if (question.length > 500) {
    showToast('La pregunta no puede superar los 500 caracteres.');
    return;
  }

  hideSections();
  setLoading(true, 'Consultando...');

  try {
    const res = await fetch('/api/v1/ceo/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    // data: { answer, confidence, sources }

    renderQueryAnswer(data);
    setLoading(false, '');
    await playTTS(data.answer);
  } catch (err) {
    console.error('CEO query error:', err);
    showToast('Error al consultar: ' + err.message);
    setLoading(false, '');
  }
}

function renderQueryAnswer(data) {
  answerText.textContent = data.answer;
  renderConfidenceBadge(data.confidence);
  answerMeta.textContent = '';
  renderSources(data.sources);
  answerSection.classList.add('visible');
}

// ─── CEO Summary ──────────────────────────────────────────────────────────────
async function fetchSummary() {
  hideSections();
  setLoading(true, 'Generando briefing...');

  try {
    const res = await fetch('/api/v1/ceo/summary');
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    // data: { summary, checkins_count, period }

    renderSummary(data);
    setLoading(false, '');
    await playTTS(data.summary);
  } catch (err) {
    console.error('CEO summary error:', err);
    showToast('Error al obtener el briefing: ' + err.message);
    setLoading(false, '');
  }
}

function renderSummary(data) {
  summaryText.textContent = data.summary;
  summaryMeta.innerHTML = `
    <span class="summary-stat">
      <strong>${data.checkins_count}</strong> check-in${data.checkins_count !== 1 ? 's' : ''} completados
    </span>
    <span class="summary-stat">Período: <strong>${escapeHtml(data.period)}</strong></span>
  `;
  summarySection.classList.add('visible');
}

function hideSections() {
  answerSection.classList.remove('visible');
  summarySection.classList.remove('visible');
  if (sourcesSection) sourcesSection.style.display = 'none';
  lastAnswerBlob = null;
}

// ─── Button listeners ─────────────────────────────────────────────────────────
btnQuery.addEventListener('click', submitQuery);

btnSummary.addEventListener('click', fetchSummary);

queryInput.addEventListener('keydown', (e) => {
  // Ctrl+Enter or Cmd+Enter submits
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    submitQuery();
  }
});

// ─── Voice recording ──────────────────────────────────────────────────────────
function supportsMediaRecorder() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
}

btnVoice.addEventListener('click', async () => {
  if (isLoading) return;
  if (!supportsMediaRecorder()) {
    showToast('Tu navegador no soporta grabación de voz. Escribe tu pregunta.');
    return;
  }
  if (isRecording) {
    stopVoiceRecording();
  } else {
    await startVoiceRecording();
  }
});

async function startVoiceRecording() {
  try {
    const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : '';

    mediaRecorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);

    audioChunks = [];
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      await handleVoiceRecordingStop();
    };

    mediaRecorder.start(100);
    isRecording = true;

    btnVoice.classList.add('recording');
    btnVoice.setAttribute('aria-label', 'Detener grabación de voz');
    statusLabel.textContent = 'Grabando... haz clic en el micrófono para detener';
    statusLabel.className   = 'status-label recording';
  } catch (err) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showToast('Permiso de micrófono denegado. Escribe tu pregunta.');
    } else {
      showToast('No se pudo acceder al micrófono: ' + err.message);
    }
  }
}

function stopVoiceRecording() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  btnVoice.classList.remove('recording');
  btnVoice.setAttribute('aria-label', 'Grabar pregunta por voz');
  statusLabel.textContent = 'Procesando audio...';
  statusLabel.className   = 'status-label processing';
  mediaRecorder.stop();
}

async function handleVoiceRecordingStop() {
  if (!audioChunks.length) {
    statusLabel.textContent = '';
    showToast('No se detectó audio. Inténtalo de nuevo.');
    return;
  }

  setLoading(true, 'Transcribiendo voz...');

  try {
    const blob     = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');

    const res = await fetch('/api/v1/speech/transcribe', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `STT error ${res.status}`);
    }

    const { transcript } = await res.json();
    if (transcript && transcript.trim()) {
      queryInput.value = transcript.trim();
      queryInput.dispatchEvent(new Event('input'));
      statusLabel.textContent = 'Voz transcrita. Revisa y haz clic en Preguntar.';
      statusLabel.className   = 'status-label success';
    } else {
      showToast('No se detectó ninguna palabra. Inténtalo de nuevo.');
      statusLabel.textContent = '';
    }
  } catch (err) {
    console.error('Voice transcription error:', err);
    showToast('Error de transcripción: ' + err.message);
    statusLabel.textContent = '';
  } finally {
    setLoading(false, statusLabel.textContent);
  }
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
if (!supportsMediaRecorder()) {
  btnVoice.disabled = true;
  btnVoice.title    = 'Tu navegador no soporta grabación de voz';
  btnVoice.setAttribute('aria-label', 'Grabación de voz no disponible en este navegador');
}
