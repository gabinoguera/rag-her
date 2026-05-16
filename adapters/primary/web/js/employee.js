/**
 * employee.js — Lógica del flujo de check-in de empleados (4 turnos).
 *
 * Flujo:
 *   1. Al cargar: POST /api/v1/checkin/start → obtiene session_id + primera pregunta
 *   2. Reproduce pregunta vía TTS
 *   3. Usuario graba respuesta (MediaRecorder) o la escribe (fallback)
 *   4. POST /api/v1/speech/transcribe → muestra transcripción
 *   5. Usuario confirma → POST /api/v1/checkin/{session_id}/answer
 *   6. Si is_complete: pantalla de confirmación; si no: siguiente pregunta (volver a 2)
 *
 * Total de turnos: 4 (turn 0 captura nombre, turns 1-3 son preguntas de check-in)
 */

'use strict';

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const questionEl      = document.getElementById('question-text');
const statusLabel     = document.getElementById('status-label');
const progressLabel   = document.getElementById('progress-label');
const progressBar     = document.getElementById('progress-bar');
const btnRecord       = document.getElementById('btn-record');
const recordLabel     = document.getElementById('record-label');
const transcriptEl    = document.getElementById('transcript');
const btnConfirm      = document.getElementById('btn-confirm');
const btnReplay       = document.getElementById('btn-replay');
const checkinForm     = document.getElementById('checkin-form');
const completionScreen = document.getElementById('completion-screen');
const completionName  = document.getElementById('completion-name');
const toastEl         = document.getElementById('toast');
const fallbackWrap    = document.getElementById('fallback-wrap');
const textFallback    = document.getElementById('text-fallback');
const btnSubmitText   = document.getElementById('btn-submit-text');

// ─── State ────────────────────────────────────────────────────────────────────
let sessionId       = null;
let currentTurn     = 0;       // 1-based after start (1 to 4)
const TOTAL_TURNS   = 4;
let mediaRecorder   = null;
let audioChunks     = [];
let currentTranscript = '';
let lastTtsBlob     = null;    // cached TTS audio for replay
let isRecording     = false;
let isProcessing    = false;

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

// ─── Utility: set UI state ────────────────────────────────────────────────────
function setStatus(text, type = '') {
  statusLabel.textContent = text;
  statusLabel.className   = 'status-label' + (type ? ` ${type}` : '');
}

function setLoading(busy) {
  isProcessing = busy;
  btnRecord.disabled    = busy;
  btnConfirm.disabled   = busy;
  btnSubmitText.disabled = busy;
}

// ─── Progress bar helpers ─────────────────────────────────────────────────────
function updateProgress(turn) {
  // turn: 1-based number of current turn (after start, this is 1)
  const steps = progressBar.querySelectorAll('.step');
  const lines = progressBar.querySelectorAll('.step-line');
  steps.forEach((step, i) => {
    const stepNum = i + 1;
    step.classList.remove('active', 'done');
    if (stepNum < turn)  step.classList.add('done');
    if (stepNum === turn) step.classList.add('active');
  });
  lines.forEach((line, i) => {
    line.classList.toggle('done', i + 1 < turn);
  });
  progressLabel.textContent = `Pregunta ${turn} de ${TOTAL_TURNS}`;
  progressBar.setAttribute('aria-valuenow', String(turn));
}

// ─── TTS: play question ───────────────────────────────────────────────────────
async function playTTS(text) {
  try {
    setStatus('Reproduciendo pregunta...', 'playing');
    const res = await fetch('/api/v1/speech/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      // TTS failure is non-fatal — user can still read the question
      console.warn('TTS falló con status', res.status);
      setStatus('');
      return;
    }
    lastTtsBlob = await res.blob();
    const audioUrl = URL.createObjectURL(lastTtsBlob);
    const audio = new Audio(audioUrl);
    audio.onended = () => {
      setStatus('');
      URL.revokeObjectURL(audioUrl);
    };
    await audio.play();
    btnReplay.classList.remove('hidden');
  } catch (err) {
    console.warn('TTS error (non-fatal):', err);
    setStatus('');
  }
}

// ─── Replay last TTS ─────────────────────────────────────────────────────────
btnReplay.addEventListener('click', async () => {
  if (!lastTtsBlob) return;
  try {
    const audioUrl = URL.createObjectURL(lastTtsBlob);
    const audio = new Audio(audioUrl);
    audio.onended = () => URL.revokeObjectURL(audioUrl);
    setStatus('Reproduciendo...', 'playing');
    await audio.play();
    audio.onended = () => { setStatus(''); URL.revokeObjectURL(audioUrl); };
  } catch (err) {
    console.warn('Replay error:', err);
  }
});

// ─── MediaRecorder setup ──────────────────────────────────────────────────────
function supportsMediaRecorder() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
}

function showFallback() {
  btnRecord.style.display  = 'none';
  fallbackWrap.classList.add('visible');
}

async function startRecording() {
  if (isRecording || isProcessing) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
      await handleRecordingStop();
    };

    mediaRecorder.start(100); // collect data every 100ms
    isRecording = true;

    btnRecord.classList.add('recording');
    recordLabel.textContent = 'Parar';
    btnRecord.setAttribute('aria-label', 'Detener grabación');
    setStatus('Grabando... haz clic para detener', 'recording');
    transcriptEl.textContent = '';
    btnConfirm.classList.add('hidden');
  } catch (err) {
    console.error('getUserMedia error:', err);
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showToast('Permiso de micrófono denegado. Escribe tu respuesta.');
      showFallback();
    } else {
      showToast('No se pudo acceder al micrófono: ' + err.message);
    }
  }
}

function stopRecording() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  btnRecord.classList.remove('recording');
  btnRecord.classList.add('processing');
  recordLabel.textContent = 'Procesando...';
  btnRecord.disabled = true;
  setStatus('Procesando audio...', 'processing');
  mediaRecorder.stop();
}

async function handleRecordingStop() {
  if (!audioChunks.length) {
    setStatus('');
    resetRecordButton();
    showToast('No se detectó audio. Inténtalo de nuevo.');
    return;
  }

  const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
  await transcribeAudio(blob);
}

// ─── Record button click ──────────────────────────────────────────────────────
btnRecord.addEventListener('click', () => {
  if (isProcessing) return;
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

function resetRecordButton() {
  btnRecord.classList.remove('recording', 'processing');
  btnRecord.disabled = false;
  recordLabel.textContent = 'Hablar';
  btnRecord.setAttribute('aria-label', 'Mantén pulsado para hablar o haz clic para iniciar/detener grabación');
}

// ─── Transcribe audio ─────────────────────────────────────────────────────────
async function transcribeAudio(blob) {
  setLoading(true);
  setStatus('Transcribiendo...', 'processing');
  try {
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
    if (!transcript || !transcript.trim()) {
      showToast('No se detectó ninguna palabra. Inténtalo de nuevo.');
      setStatus('');
      resetRecordButton();
      setLoading(false);
      return;
    }

    currentTranscript = transcript.trim();
    transcriptEl.textContent = currentTranscript;
    btnConfirm.classList.remove('hidden');
    setStatus('Revisa tu respuesta y confirma', 'success');
    resetRecordButton();
  } catch (err) {
    console.error('Transcription error:', err);
    showToast('Error de transcripción: ' + err.message);
    setStatus('');
    resetRecordButton();
  } finally {
    setLoading(false);
  }
}

// ─── Text fallback submit ──────────────────────────────────────────────────────
btnSubmitText.addEventListener('click', () => {
  const text = textFallback.value.trim();
  if (!text) {
    showToast('Por favor escribe tu respuesta antes de enviar.');
    return;
  }
  currentTranscript = text;
  transcriptEl.textContent = currentTranscript;
  btnConfirm.classList.remove('hidden');
  setStatus('Revisa tu respuesta y confirma', 'success');
});

textFallback.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    btnSubmitText.click();
  }
});

// ─── Confirm and submit answer ─────────────────────────────────────────────────
btnConfirm.addEventListener('click', async () => {
  if (!currentTranscript || !sessionId) return;
  await submitAnswer(currentTranscript);
});

async function submitAnswer(answerText) {
  setLoading(true);
  setStatus('Enviando respuesta...', 'processing');
  btnConfirm.classList.add('hidden');
  try {
    const res = await fetch(`/api/v1/checkin/${sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer_text: answerText }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `API error ${res.status}`);
    }

    const data = await res.json();
    // data: { next_question_text, is_complete, employee_name }

    if (data.is_complete) {
      showCompletion(data.employee_name || 'Empleado');
    } else {
      currentTurn += 1;
      updateProgress(currentTurn);
      await showNextQuestion(data.next_question_text);
    }
  } catch (err) {
    console.error('Answer submit error:', err);
    showToast('Error al enviar respuesta: ' + err.message);
    btnConfirm.classList.remove('hidden');
    setStatus('');
  } finally {
    setLoading(false);
    currentTranscript = '';
    textFallback.value = '';
    transcriptEl.textContent = '';
  }
}

// ─── Show next question ────────────────────────────────────────────────────────
async function showNextQuestion(text) {
  questionEl.classList.add('loading');
  questionEl.textContent = text;
  questionEl.classList.remove('loading');
  btnReplay.classList.add('hidden');
  lastTtsBlob = null;
  setStatus('');
  await playTTS(text);
}

// ─── Completion screen ─────────────────────────────────────────────────────────
function showCompletion(name) {
  currentTurn = TOTAL_TURNS;
  updateProgress(TOTAL_TURNS);

  // Mark all steps done
  progressBar.querySelectorAll('.step').forEach(s => {
    s.classList.remove('active');
    s.classList.add('done');
  });
  progressBar.querySelectorAll('.step-line').forEach(l => l.classList.add('done'));

  checkinForm.classList.add('hidden');
  completionName.textContent = `¡Gracias, ${name}!`;
  completionScreen.classList.add('visible');
  progressLabel.textContent = 'Check-in completado';
}

// ─── Init: start check-in session ─────────────────────────────────────────────
async function initCheckin() {
  // Check MediaRecorder availability
  if (!supportsMediaRecorder()) {
    showFallback();
  }

  questionEl.textContent = 'Iniciando check-in...';
  questionEl.classList.add('loading');
  setStatus('Conectando...', 'processing');
  updateProgress(1);

  try {
    const res = await fetch('/api/v1/checkin/start', { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Error ${res.status}`);
    }
    const data = await res.json();
    // data: { session_id, question_text }

    sessionId    = data.session_id;
    currentTurn  = 1;

    questionEl.classList.remove('loading');
    questionEl.textContent = data.question_text;
    setStatus('');
    updateProgress(1);

    await playTTS(data.question_text);
  } catch (err) {
    console.error('Init error:', err);
    questionEl.classList.remove('loading');
    questionEl.textContent = 'Error al conectar con el servidor.';
    setStatus('Error de conexión', '');
    showToast('No se pudo iniciar el check-in: ' + err.message);
  }
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
initCheckin();
