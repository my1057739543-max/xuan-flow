const fs = require('fs');

function readInput() {
  try {
    const raw = fs.readFileSync(0, 'utf8');
    return raw && raw.trim() ? JSON.parse(raw) : {};
  } catch (err) {
    return {};
  }
}

function analyzeText(text) {
  const safeText = typeof text === 'string' ? text : '';
  const lines = safeText.length === 0 ? 0 : safeText.split(/\r?\n/).length;
  const words = safeText.trim().length === 0 ? 0 : safeText.trim().split(/\s+/).length;
  return {
    chars: safeText.length,
    words,
    lines,
    preview: safeText.slice(0, 120)
  };
}

const input = readInput();
const result = {
  ok: true,
  skill: 'text-utils-basic',
  analysis: analyzeText(input.text)
};

process.stdout.write(JSON.stringify(result));
