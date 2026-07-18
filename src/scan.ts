import * as fs from 'fs';
import * as path from 'path';
import { DroperOG } from './index';
import { TelegramNotifier } from './telegram';

interface State {
  knownIds: string[];
  totalProjects: number;
  lastRun: string;
}

const STATE_FILE = path.join(__dirname, '..', 'data', 'state.json');

function loadState(): State {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    }
  } catch { /* ignore */ }
  return { knownIds: [], totalProjects: 0, lastRun: '' };
}

function saveState(state: State): void {
  const dir = path.dirname(STATE_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

async function main() {
  console.log('DroperOG — Telegram Scanner\n');

  const app = new DroperOG(process.env.COINRANKING_API_KEY);
  const telegram = new TelegramNotifier();
  const state = loadState();

  // Restore known IDs
  for (const id of state.knownIds) {
    app.knownIds.add(id);
  }

  const allProjects = await app.runOnce();

  // Collect new projects
  const newProjects = allProjects.filter(p => !state.knownIds.includes(p.id));

  const summary = {
    total: app.projects.length,
    trusted: app.projects.filter(p => p.trustScore >= 70).length,
    newCount: newProjects.length,
  };

  // Notify
  if (newProjects.length > 0) {
    await telegram.notifyNewProjects(newProjects);
  }
  await telegram.notifySummary(summary.total, summary.trusted, summary.newCount);

  // Update state
  const updatedState: State = {
    knownIds: [...new Set([...state.knownIds, ...allProjects.map(p => p.id)])],
    totalProjects: summary.total,
    lastRun: new Date().toISOString(),
  };
  saveState(updatedState);
  console.log(`\nState saved: ${updatedState.knownIds.length} known IDs`);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
