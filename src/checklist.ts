import * as fs from 'fs';
import * as path from 'path';
import { AirdropProject, ChecklistItem, ProjectChecklist } from './types';
import { generateId } from './utils';

const DATA_DIR = path.join(__dirname, '..', 'data');
const FILE_PATH = path.join(DATA_DIR, 'checklist.json');

const SOCIAL_PLATFORMS = ['twitter', 'discord', 'telegram', 'medium'];

const DEADLINE_KEYWORDS: [RegExp, number?][] = [
  [/claim\s*(by|before|until)\s*(\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4})/i],
  [/(deadline|ends?)\s*(\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4})/i],
  [/snapshot\s*(by|on|before)\s*(\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4})/i],
];

function parseDateFromText(text: string): number | undefined {
  for (const [pattern] of DEADLINE_KEYWORDS) {
    const match = text.match(pattern);
    if (match) {
      const dateStr = match[2] || match[1];
      const parsed = Date.parse(dateStr);
      if (!isNaN(parsed)) return parsed;
    }
  }

  const dateMatch = text.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (dateMatch) {
    const parsed = Date.parse(`${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`);
    if (!isNaN(parsed)) return parsed;
  }

  return undefined;
}

export class ChecklistManager {
  private data: Map<string, ProjectChecklist> = new Map();

  constructor() {
    this.load();
  }

  private load(): void {
    try {
      if (fs.existsSync(FILE_PATH)) {
        const raw = JSON.parse(fs.readFileSync(FILE_PATH, 'utf-8'));
        if (Array.isArray(raw)) {
          for (const entry of raw) {
            this.data.set(entry.projectId, entry);
          }
        }
      }
    } catch { /* ignore */ }
  }

  private save(): void {
    const dir = path.dirname(FILE_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(FILE_PATH, JSON.stringify(Array.from(this.data.values()), null, 2));
  }

  getOrCreate(project: AirdropProject): ProjectChecklist {
    const existing = this.data.get(project.id);
    if (existing) return existing;

    const items: ChecklistItem[] = [];
    const now = Date.now();

    // Follow social accounts
    for (const platform of SOCIAL_PLATFORMS) {
      const url = project.links[platform as keyof typeof project.links];
      if (url) {
        items.push({
          id: generateId('task'),
          task: `Follow on ${platform.charAt(0).toUpperCase() + platform.slice(1)}`,
          type: 'social',
          completed: false,
        });
      }
    }

    // Check for claim deadline
    const deadlineFromTimeline = project.timeline?.claimEndDate || project.timeline?.claimStartDate;
    if (deadlineFromTimeline) {
      items.push({
        id: generateId('task'),
        task: deadlineFromTimeline > now ? 'Claim tokens' : 'Check claim status',
        type: 'claim',
        deadline: deadlineFromTimeline,
        completed: deadlineFromTimeline < now,
      });
    }

    // Auto-detect tasks from description
    if (project.description) {
      const desc = project.description.toLowerCase();

      if (desc.includes('bridge') || desc.includes('bridge to')) {
        items.push({ id: generateId('task'), task: 'Bridge assets to network', type: 'bridge', completed: false });
      }
      if (desc.includes('stak') || desc.includes('delegate')) {
        items.push({ id: generateId('task'), task: 'Stake / delegate tokens', type: 'stake', completed: false });
      }
      if (desc.includes('swap') || desc.includes('trade on')) {
        items.push({ id: generateId('task'), task: 'Perform swap / trade', type: 'swap', completed: false });
      }
      if (desc.includes('transact') || desc.includes('transaction') || desc.includes('use the')) {
        items.push({ id: generateId('task'), task: 'Complete on-chain transactions', type: 'transaction', completed: false });
      }

      const extractedDeadline = parseDateFromText(project.description);
      if (extractedDeadline && !deadlineFromTimeline) {
        items.push({
          id: generateId('task'),
          task: 'Complete tasks before deadline',
          type: 'claim',
          deadline: extractedDeadline,
          completed: extractedDeadline < now,
        });
      }
    }

    const checklist: ProjectChecklist = {
      projectId: project.id,
      projectName: project.name,
      items,
      createdAt: now,
      updatedAt: now,
    };

    this.data.set(project.id, checklist);
    this.save();
    return checklist;
  }

  completeTask(projectId: string, taskId: string): boolean {
    const checklist = this.data.get(projectId);
    if (!checklist) return false;

    const item = checklist.items.find(i => i.id === taskId);
    if (!item) return false;

    item.completed = true;
    item.completedAt = Date.now();
    checklist.updatedAt = Date.now();
    this.save();
    return true;
  }

  uncompleteTask(projectId: string, taskId: string): boolean {
    const checklist = this.data.get(projectId);
    if (!checklist) return false;

    const item = checklist.items.find(i => i.id === taskId);
    if (!item) return false;

    item.completed = false;
    item.completedAt = undefined;
    checklist.updatedAt = Date.now();
    this.save();
    return true;
  }

  addCustomTask(projectId: string, task: string, type: ChecklistItem['type'] = 'other', deadline?: number): ChecklistItem | null {
    const checklist = this.data.get(projectId);
    if (!checklist) return null;

    const item: ChecklistItem = {
      id: generateId('task'),
      task,
      type,
      deadline,
      completed: false,
    };

    checklist.items.push(item);
    checklist.updatedAt = Date.now();
    this.save();
    return item;
  }

  getProjectChecklist(projectId: string): ProjectChecklist | undefined {
    return this.data.get(projectId);
  }

  getDeadlineAlerts(daysAhead: number = 7): { project: ProjectChecklist; item: ChecklistItem }[] {
    const now = Date.now();
    const limit = now + daysAhead * 86400000;
    const alerts: { project: ProjectChecklist; item: ChecklistItem }[] = [];

    for (const checklist of this.data.values()) {
      for (const item of checklist.items) {
        if (item.completed) continue;
        if (item.deadline && item.deadline > now && item.deadline < limit) {
          alerts.push({ project: checklist, item });
        }
      }
    }

    alerts.sort((a, b) => a.item.deadline! - b.item.deadline!);
    return alerts;
  }

  getUpcomingDeadlines(daysAhead: number = 14): { project: ProjectChecklist; item: ChecklistItem }[] {
    const now = Date.now();
    const limit = now + daysAhead * 86400000;
    const items: { project: ProjectChecklist; item: ChecklistItem }[] = [];

    for (const checklist of this.data.values()) {
      for (const item of checklist.items) {
        if (item.completed) continue;
        if (item.deadline && item.deadline < limit) {
          items.push({ project: checklist, item });
        }
      }
    }

    items.sort((a, b) => a.item.deadline! - b.item.deadline!);
    return items;
  }

  getStats(): { total: number; completed: number; pending: number; deadlinesNear: number } {
    let total = 0;
    let completed = 0;
    let deadlinesNear = 0;
    const now = Date.now();
    const limit = now + 7 * 86400000;

    for (const checklist of this.data.values()) {
      for (const item of checklist.items) {
        total++;
        if (item.completed) completed++;
        else if (item.deadline && item.deadline < limit) deadlinesNear++;
      }
    }

    return { total, completed, pending: total - completed, deadlinesNear };
  }

  printChecklist(projectId: string): void {
    const checklist = this.data.get(projectId);
    if (!checklist) {
      console.log('  No checklist for this project.');
      return;
    }

    console.log(`  📋 Checklist: ${checklist.projectName}`);
    for (const item of checklist.items) {
      const status = item.completed ? '✅' : '⬜';
      const deadline = item.deadline ? ` (by ${new Date(item.deadline).toLocaleDateString()})` : '';
      console.log(`  ${status} ${item.task}${deadline}`);
    }
    const done = checklist.items.filter(i => i.completed).length;
    console.log(`  Progress: ${done}/${checklist.items.length} tasks completed`);
  }

  printDeadlineAlerts(): void {
    const alerts = this.getDeadlineAlerts(7);
    if (alerts.length === 0) {
      console.log('  ✅ No approaching deadlines in the next 7 days.');
      return;
    }

    console.log(`\n  ⏰ DEADLINE ALERTS (${alerts.length} upcoming):`);
    for (const { project, item } of alerts) {
      const daysLeft = Math.ceil((item.deadline! - Date.now()) / 86400000);
      const emoji = daysLeft <= 1 ? '🔴' : daysLeft <= 3 ? '🟠' : '🟡';
      console.log(`  ${emoji} ${project.projectName}: "${item.task}" — ${daysLeft}d left`);
    }
    console.log('');
  }
}
