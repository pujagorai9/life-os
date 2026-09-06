'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import Image from 'next/image';
import {
  ArrowLeft,
  BarChart3,
  BookOpen,
  Bot,
  BriefcaseBusiness,
  Camera,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  Dumbbell,
  HeartHandshake,
  House,
  Landmark,
  LoaderCircle,
  MessageCircle,
  Monitor,
  Moon,
  Newspaper,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Sun,
  TriangleAlert,
  Utensils,
  Watch,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';

type View =
  | 'today'
  | 'check-in'
  | 'agents'
  | 'progress'
  | 'briefing'
  | 'appointment-sync'
  | 'finance';

type ThemePreference = 'system' | 'light' | 'dark';

type Agent = {
  id: string;
  name: string;
  domain: string;
  purpose: string;
};

type Goal = {
  id: string;
  domain: string;
  owner_agent: string;
  title: string;
  success_definition: string;
  start_at: string;
  review_at: string;
  status: string;
  metrics: GoalMetric[];
  routines: GoalRoutine[];
};

type GoalMetric = {
  key: string;
  label: string;
  unit: string;
  target_type: 'exact' | 'at_least' | 'at_most' | 'range';
  target_value: number | null;
  minimum_value: number | null;
  maximum_value: number | null;
  cadence: string;
};

type GoalRoutine = {
  title: string;
  cadence: string;
  target_count: number;
  unit: string;
  preferred_time: string | null;
  kind: 'user_commitment' | 'agent_delivery';
};

type CheckIn = {
  id: string;
  goal_id: string;
  prompt_id: string;
  agent_id: string;
  prompt: string;
  due_at: string;
  kind?: 'user_commitment' | 'agent_delivery';
  input_required?: boolean | null;
  status: 'pending' | 'delivered' | 'responded' | 'skipped';
  outcome?: 'done' | 'partial' | null;
  completed_at?: string | null;
  status_updated_at?: string | null;
};

type LogConfirmation = {
  title: string;
  message: string;
  updatedCheckIn: CheckIn;
  updatedProgress: ProgressSummary;
  hasNextTask: boolean;
};

type ProgressSummary = {
  commitments_total: number;
  commitments_done: number;
  completion_rate: number;
  by_status: Record<string, number>;
  event_totals: Record<string, number>;
};

type ProgressEvent = {
  id: string;
  domain: string;
  metric: string;
  value: number;
  unit: string;
  source: string;
  confidence: number;
  metadata: Record<string, unknown>;
  occurred_at: string;
};

type WhoopStatus = {
  configured: boolean;
  connected: boolean;
  scope: string[];
  has_refresh_token: boolean;
};

type WhoopSyncResult = {
  connected: boolean;
  created_events: number;
  skipped_existing: number;
  imported_days: string[];
};

type RingMetric = {
  label: string;
  value: number;
  target: number | null;
  unit: string;
  color: string;
  targetLabel?: string;
};

type BinaryMetric = {
  label: string;
  complete: boolean;
  unavailable?: boolean;
};

type BriefingDocument = {
  day: string;
  title: string;
  markdown: string;
  source_file: string;
};

type AppointmentSyncItem = {
  action: string;
  outcome: string;
  summary: string;
  event_date: string | null;
  event_time: string | null;
  exception: boolean;
};

type AppointmentSyncDocument = {
  day: string;
  processed_at: string;
  cutoff_at: string | null;
  emails_processed: number;
  events_created: number;
  events_updated: number;
  events_cancelled: number;
  existing_events_matched: number;
  items: AppointmentSyncItem[];
};

type ExpenseRecord = {
  id: string;
  transaction_at: string;
  merchant: string;
  category: string;
  amount: number;
  currency: string;
  kind: 'purchase' | 'refund';
  confidence: number;
  household_member?: string | null;
};

type FinanceEmailAccount = {
  account_id: string;
  email: string;
  member_name: string;
  connected_at: string;
  scopes: string[];
};

type FinanceCategoryTotal = {
  category: string;
  amount: number;
};

type FinanceCurrencySummary = {
  currency: string;
  total_spent: number;
  total_refunded: number;
  net_spent: number;
  categories: FinanceCategoryTotal[];
};

type FinanceDailyReport = {
  day: string;
  purchase_count: number;
  processed_email_count: number;
  summaries: FinanceCurrencySummary[];
  transactions: ExpenseRecord[];
};

type KnowledgeRecord = {
  id: string;
  studied_at: string;
  source_title: string;
  topic: string;
  probe_answers: string[];
  confirmed: boolean;
};

type WellbeingDraft = {
  accomplishments: string;
  gratitude: string;
  morningAffirmations: boolean;
  meditationComplete: boolean;
  oneAction: string;
  emotionalDump: string;
  actionCompleted: boolean | null;
  eveningAffirmations: boolean;
};

type NutritionReviewDraft = {
  hunger: 'comfortable' | 'hungrier' | 'persistent' | null;
  energy: 'steady' | 'low' | 'weak_dizzy' | null;
  breastfeeding: 'none' | 'reduced_supply' | 'other' | null;
};

type NutritionTotals = {
  calories: number;
  protein: number;
  carbohydrates: number;
  fat: number;
  fiber: number;
  calcium: number;
};

type ResumeState = {
  day: string;
  view: View;
  selectedCheckInId: string | null;
  selectedAgentId: string | null;
  showFullPlan: boolean;
  checkInResponse: string;
  chatDraft: string;
  messages: Record<string, ChatMessage[]>;
  wellbeingStep: number;
  wellbeingDraft: WellbeingDraft;
  meditationSeconds: number;
  meditationRunning: boolean;
  morningAction: string;
  nutritionMessages: Record<string, NutritionMessage[]>;
  nutritionAnalyses: Record<string, PhotoAnalysis>;
  nutritionReviewDraft: NutritionReviewDraft;
  logConfirmation: LogConfirmation | null;
};

type AgentReply = {
  agent_id: string;
  summary: string;
  questions: string[];
  warnings: string[];
};

type ChatMessage = { role: 'user' | 'assistant'; text: string };

type NutritionMessage = {
  role: 'user' | 'assistant';
  text: string;
  analysis?: PhotoAnalysis;
  imagePreviews?: string[];
};

type NutritionDraftImage = { file: File; preview: string };

type NutritionConversationResult = {
  photos: CheckInPhoto[];
  analysis: PhotoAnalysis;
};

type PhotoAnalysis = {
  summary: string;
  observations: string[];
  estimated_calories: number | null;
  estimated_protein_g: number | null;
  estimated_carbohydrates_g: number | null;
  estimated_fat_g: number | null;
  estimated_fiber_g: number | null;
  estimated_calcium_mg: number | null;
  confidence: number;
  caveats: string[];
};

type CheckInPhoto = {
  id: string;
  check_in_id: string;
  agent_id: string;
  media_type: string;
  size_bytes: number;
  analysis_status: 'not_requested' | 'completed' | 'unavailable';
  analysis: PhotoAnalysis | null;
  created_at: string;
};

const TENANT_ID = process.env.NEXT_PUBLIC_LIFE_OS_TENANT_ID || 'me';
const RESUME_STATE_KEY = `life-os-resume:${TENANT_ID}`;
const LIFE_OS_START_DAY = '2026-08-30';

const todayKey = () => {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-');
};

const clampLifeOSDay = (day: string) =>
  day < LIFE_OS_START_DAY
    ? LIFE_OS_START_DAY
    : day > todayKey()
      ? todayKey()
      : day;

const localDateFromKey = (day: string) => {
  const [year, month, date] = day.split('-').map(Number);
  return new Date(year, month - 1, date, 12, 0, 0, 0);
};

const shiftDay = (day: string, amount: number) => {
  const date = localDateFromKey(day);
  date.setDate(date.getDate() + amount);
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
};

const dayBounds = (day: string) => {
  const start = localDateFromKey(day);
  start.setHours(0, 0, 0, 0);
  const end = localDateFromKey(day);
  end.setHours(23, 59, 59, 999);
  return { start, end };
};

const readResumeState = (): ResumeState | null => {
  try {
    const value = window.localStorage.getItem(RESUME_STATE_KEY);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<ResumeState>;
    if (!parsed.day || !/^\d{4}-\d{2}-\d{2}$/.test(parsed.day)) return null;
    if (
      ![
        'today',
        'check-in',
        'agents',
        'progress',
        'briefing',
        'appointment-sync',
        'finance',
      ].includes(
        parsed.view || '',
      )
    ) {
      return null;
    }
    return parsed as ResumeState;
  } catch {
    return null;
  }
};

const AFFIRMATIONS = [
  'I am so happy and grateful that I deeply belong in my work.',
  'I am so happy and grateful that I wake up excited about what I do.',
  'I am so happy and grateful that I mother with ease and joy.',
  'I am so happy and grateful that I feel deeply connected in my relationships.',
  'I am so happy and grateful that my body feels strong and alive.',
];

const EMPTY_WELLBEING_DRAFT: WellbeingDraft = {
  accomplishments: '',
  gratitude: '',
  morningAffirmations: false,
  meditationComplete: false,
  oneAction: '',
  emotionalDump: '',
  actionCompleted: null,
  eveningAffirmations: false,
};

const EMPTY_NUTRITION_REVIEW_DRAFT: NutritionReviewDraft = {
  hunger: null,
  energy: null,
  breastfeeding: null,
};

const EMPTY_NUTRITION_TOTALS: NutritionTotals = {
  calories: 0,
  protein: 0,
  carbohydrates: 0,
  fat: 0,
  fiber: 0,
  calcium: 0,
};

const agentStyles: Record<string, { icon: typeof Sparkles; tint: string }> = {
  chief_of_staff: { icon: Sparkles, tint: 'bg-emerald-100 text-emerald-800' },
  career_coach: { icon: BriefcaseBusiness, tint: 'bg-blue-100 text-blue-800' },
  knowledge_guru: { icon: BookOpen, tint: 'bg-amber-100 text-amber-800' },
  briefing_intern: { icon: Newspaper, tint: 'bg-violet-100 text-violet-800' },
  nutrition_coach: { icon: Utensils, tint: 'bg-orange-100 text-orange-800' },
  fitness_coach: { icon: Dumbbell, tint: 'bg-cyan-100 text-cyan-800' },
  inner_wellbeing_guru: {
    icon: HeartHandshake,
    tint: 'bg-rose-100 text-rose-800',
  },
  operations_manager: { icon: House, tint: 'bg-lime-100 text-lime-800' },
  chief_accountability_officer: {
    icon: Check,
    tint: 'bg-teal-100 text-teal-800',
  },
  head_of_performance_analytics: {
    icon: BarChart3,
    tint: 'bg-indigo-100 text-indigo-800',
  },
  chief_finance_officer: {
    icon: Landmark,
    tint: 'bg-emerald-100 text-emerald-800',
  },
  chief_archivist: { icon: BookOpen, tint: 'bg-stone-200 text-stone-800' },
};

const formatAgent = (id: string) =>
  id
    .split('_')
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(' ');

const friendlyPrompt = (prompt: string) =>
  prompt
    .replace(/^Did you complete '[^']+'\? Minimum success:\s*/i, '')
    .replace(/^Operations Manager check-in:\s*/i, '')
    .replace(/^Prepare and deliver:\s*/i, '')
    .trim();

const isAgentDelivery = (checkIn: CheckIn) =>
  checkIn.kind === 'agent_delivery' ||
  checkIn.prompt.trimStart().startsWith('Prepare and deliver:');

const isAppointmentSyncDelivery = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'operations_manager' &&
  isAgentDelivery(checkIn) &&
  checkIn.prompt.toLowerCase().includes('appointment and calendar sync');

const isFinanceDelivery = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'chief_finance_officer' && isAgentDelivery(checkIn);

const supportsPhoto = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'nutrition_coach' ||
  checkIn?.agent_id === 'fitness_coach' ||
  checkIn?.agent_id === 'knowledge_guru' ||
  checkIn?.agent_id === 'career_coach';

const supportsPrivateAttachment = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'knowledge_guru' ||
  checkIn?.agent_id === 'career_coach';

const usesInputLogging = (checkIn: CheckIn) => {
  if (checkIn.input_required !== null && checkIn.input_required !== undefined) {
    return checkIn.input_required;
  }
  const prompt = checkIn.prompt.toLowerCase();
  return (
    checkIn.agent_id === 'nutrition_coach' ||
    checkIn.agent_id === 'career_coach' ||
    checkIn.agent_id === 'chief_archivist' ||
    checkIn.agent_id === 'inner_wellbeing_guru' ||
    prompt.startsWith('today you committed to:') ||
    prompt.startsWith('how did this commitment cycle feel') ||
    prompt.includes('record total sleep') ||
    prompt.includes('record weight') ||
    prompt.includes('feed log')
  );
};

const isWakeUpRoutine = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'inner_wellbeing_guru' &&
  checkIn.prompt.toLowerCase().includes('after-waking daily mindset ritual');

const isWindDownRoutine = (checkIn?: CheckIn) =>
  checkIn?.agent_id === 'inner_wellbeing_guru' &&
  checkIn.prompt.toLowerCase().includes('before-sleep daily mindset ritual');

const isNutritionReview = (checkIn?: CheckIn) => {
  if (checkIn?.agent_id !== 'nutrition_coach') return false;
  const prompt = checkIn.prompt.toLowerCase();
  return (
    prompt.includes('daily nutrition review') ||
    prompt.includes('daily nutrition reflection') ||
    prompt.includes('nutrition and safety log')
  );
};

const deliveryTime = (dueAt: string) =>
  new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(dueAt));

const dayKeyFromInstant = (value: string) => {
  const date = new Date(value);
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
};

const compactTaskTitle = (checkIn: CheckIn) => {
  const prompt = checkIn.prompt.trim();
  const routine = prompt.match(/^Did you complete '(.+?)'\?/i);
  if (routine) return routine[1];

  const study = prompt.match(
    /^Today you were supposed to study or complete:\s*(.+?)\.\s*Expected scope:/i,
  );
  if (study) return study[1];

  const delivery = prompt.match(
    /^Prepare and deliver:\s*(.+?)\.\s*Delivery requirements:/i,
  );
  if (delivery) return delivery[1];

  if (prompt.startsWith('Operations Manager check-in:')) {
    return 'Complete today’s family and pet care check-in';
  }

  return friendlyPrompt(prompt).split(/[?.]/, 1)[0];
};

const compactTaskScope = (checkIn: CheckIn, goal?: Goal) => {
  const prompt = checkIn.prompt;
  const marker = prompt.match(
    /(?:Minimum success|Expected scope|Delivery requirements):\s*(.+)/i,
  );
  if (marker) {
    return marker[1]
      .replace(/\s+(?:First, summarize|Do not ask the user).*/i, '')
      .trim();
  }
  return goal?.success_definition || friendlyPrompt(prompt);
};

const DESCRIPTION_LIMIT = 140;

const boundedDescription = (text: string) => {
  const normalized = text.replace(/\s+/g, ' ').trim();
  const sentence = normalized
    ? `${normalized[0].toUpperCase()}${normalized.slice(1)}`
    : normalized;
  if (sentence.length < DESCRIPTION_LIMIT && !/[.!?…]$/.test(sentence)) {
    return `${sentence}.`;
  }
  if (sentence.length <= DESCRIPTION_LIMIT) return sentence;
  const candidate = sentence.slice(0, DESCRIPTION_LIMIT - 1);
  const lastSpace = candidate.lastIndexOf(' ');
  return `${candidate.slice(0, Math.max(lastSpace, 80)).trimEnd()}…`;
};

const titleCase = (text: string) => {
  const smallWords = new Set([
    'a',
    'an',
    'and',
    'at',
    'for',
    'in',
    'of',
    'or',
    'the',
    'to',
    'with',
  ]);
  return text
    .split(/\s+/)
    .map((word, index) => {
      if (/^[A-Z0-9–-]+$/.test(word) && /[A-Z]/.test(word)) return word;
      const lower = word.toLowerCase();
      if (index > 0 && smallWords.has(lower)) return lower;
      return `${word.charAt(0).toUpperCase()}${word.slice(1)}`;
    })
    .join(' ');
};

const shortTaskTitle = (checkIn: CheckIn) => {
  if (checkIn.agent_id === 'briefing_intern' && isAgentDelivery(checkIn)) {
    return 'Daily Briefing';
  }
  if (isFinanceDelivery(checkIn)) return 'Daily Expense Summary';
  const sourceTitle = compactTaskTitle(checkIn);
  const normalizedTitle = sourceTitle.toLowerCase();
  if (normalizedTitle.includes('after-waking daily mindset ritual')) {
    return 'Wake-up Routine';
  }
  if (normalizedTitle.includes('before-sleep daily mindset ritual')) {
    return 'Wind-down Routine';
  }
  if (normalizedTitle.includes('planned lunch')) return 'Lunch';
  if (normalizedTitle.includes('planned dinner')) return 'Dinner';
  if (normalizedTitle.includes('dahi and fruit snack')) return 'Morning Snack';
  if (normalizedTitle.includes('late badam milk snack')) {
    return 'Late-Night Snack';
  }
  const simplified = sourceTitle
    .replace(/^Complete (?:the |today’s |today's )?/i, '')
    .replace(/^Eat (?:the )?/i, '')
    .replace(/^Have (?:the )?/i, '')
    .replace(/^Take (?:the )?/i, '')
    .replace(/^Record total /i, '')
    .trim();
  const words = simplified.split(/\s+/);
  return titleCase(
    words.length <= 5 ? simplified : words.slice(0, 5).join(' '),
  );
};

const deliveryDescription = (checkIn: CheckIn, goal?: Goal) => {
  if (checkIn.agent_id === 'briefing_intern') {
    return boundedDescription(
      'A 5–7 item briefing from approved emails and public sources, with why each item matters, links, provenance, and a coverage ledger.',
    );
  }
  if (isFinanceDelivery(checkIn)) {
    return boundedDescription(
      'Purchase and refund emails reviewed, with total spending and a category breakdown saved privately.',
    );
  }
  return boundedDescription(compactTaskScope(checkIn, goal));
};

const completedOnTime = (checkIn: CheckIn) =>
  Boolean(
    checkIn.completed_at &&
    new Date(checkIn.completed_at).getTime() <=
      new Date(checkIn.due_at).getTime(),
  );

const formatMoney = (amount: number, currency: string) => {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
};

const formatCategory = (category: string) =>
  category
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

const fileToBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('The photo could not be read.'));
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.split(',', 2)[1] || '');
    };
    reader.readAsDataURL(file);
  });

async function lifeOS<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type'))
    headers.set('Content-Type', 'application/json');
  const response = await fetch(
    `/api/life-os?path=${encodeURIComponent(path)}`,
    {
      ...init,
      headers,
    },
  );
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Life OS returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function AgentMark({
  agentId,
  className = '',
}: {
  agentId: string;
  className?: string;
}) {
  const style = agentStyles[agentId] || {
    icon: Bot,
    tint: 'bg-stone-100 text-stone-700',
  };
  const Icon = style.icon;
  return (
    <span
      className={`flex size-10 shrink-0 items-center justify-center rounded-2xl ${style.tint} ${className}`}
    >
      <Icon className="size-5" />
    </span>
  );
}

const formatMetricNumber = (value: number) =>
  Number.isInteger(value)
    ? value.toLocaleString()
    : value.toLocaleString(undefined, { maximumFractionDigits: 1 });

const THEME_STORAGE_KEY = 'life-os-theme';

function applyThemePreference(preference: ThemePreference) {
  const dark =
    preference === 'dark' ||
    (preference === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.dataset.theme = preference;
}

function ConcentricRings({ metrics }: { metrics: RingMetric[] }) {
  const size = 200;
  const center = size / 2;
  const stroke = 12;
  const gap = 15;
  return (
    <div
      className="relative mx-auto size-[200px] shrink-0"
      aria-hidden="true"
    >
      <svg viewBox={`0 0 ${size} ${size}`} className="size-full -rotate-90">
        {metrics.map((metric, index) => {
          const radius = center - 8 - index * gap;
          const rawPercent = metric.target
            ? Math.max(0, (metric.value / metric.target) * 100)
            : 0;
          const percent = Math.min(100, rawPercent);
          const overflow = Math.min(100, Math.max(0, rawPercent - 100));
          return (
            <g key={`${metric.label}-${index}`}>
              <circle
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke="currentColor"
                strokeWidth={stroke}
                className="text-black/10 dark:text-white/15"
              />
              <circle
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke={metric.color}
                strokeWidth={stroke}
                strokeLinecap="round"
                pathLength="100"
                strokeDasharray={`${percent} 100`}
              />
              {overflow > 0 && (
                <circle
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="none"
                  stroke="white"
                  strokeOpacity="0.88"
                  strokeWidth="4"
                  strokeLinecap="round"
                  pathLength="100"
                  strokeDasharray={`${overflow} 100`}
                  className="drop-shadow-sm"
                />
              )}
            </g>
          );
        })}
      </svg>
      <div className="absolute left-1/2 top-1/2 flex size-12 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full bg-white/95 text-center shadow-sm ring-1 ring-black/10 dark:bg-zinc-950/95 dark:ring-white/15">
        <span className="text-xl font-bold leading-none tabular-nums">
          {metrics[0]?.target
            ? `${Math.round((metrics[0].value / metrics[0].target) * 100)}%`
            : '—'}
        </span>
        <span className="mt-1 max-w-12 truncate text-[8px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {metrics[0]?.label || 'Today'}
        </span>
      </div>
    </div>
  );
}

function MetricRows({ metrics }: { metrics: RingMetric[] }) {
  return (
    <div className="mt-5 grid gap-2.5">
      {metrics.map((metric) => {
        const percent = metric.target
          ? Math.round((metric.value / metric.target) * 100)
          : null;
        return (
          <div
            key={metric.label}
            className="flex items-center justify-between gap-3 rounded-2xl bg-white/65 px-3.5 py-3 ring-1 ring-black/5 dark:bg-white/5 dark:ring-white/10"
          >
            <div className="flex min-w-0 items-center gap-2.5">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: metric.color }}
              />
              <span className="truncate text-sm font-semibold">
                {metric.label}
              </span>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-sm font-bold tabular-nums">
                {formatMetricNumber(metric.value)} /{' '}
                {metric.targetLabel ||
                  (metric.target === null
                    ? 'Target not set'
                    : formatMetricNumber(metric.target))}{' '}
                {metric.unit}
              </p>
              {percent !== null && (
                <p
                  className={`text-[10px] font-semibold ${
                    percent > 100 ? '' : 'text-muted-foreground'
                  }`}
                  style={percent > 100 ? { color: metric.color } : undefined}
                >
                  {percent > 100
                    ? `${percent}% · +${percent - 100}% over`
                    : `${percent}% of target`}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BinaryStatusTiles({ metrics }: { metrics: BinaryMetric[] }) {
  return (
    <div className="mt-5 grid grid-cols-3 gap-2.5">
      {metrics.map((metric) => {
        const state = metric.unavailable
          ? 'Not scheduled'
          : metric.complete
            ? 'Complete'
            : 'Not yet';
        return (
          <div
            key={metric.label}
            className={`flex min-h-32 flex-col items-center justify-center rounded-2xl px-2 py-4 text-center ring-1 ${
              metric.complete
                ? 'bg-emerald-100/90 text-emerald-950 ring-emerald-200 dark:bg-emerald-950/45 dark:text-emerald-100 dark:ring-emerald-800'
                : 'bg-white/65 ring-black/5 dark:bg-white/5 dark:ring-white/10'
            }`}
          >
            <span
              className={`flex size-10 items-center justify-center rounded-full ${
                metric.complete
                  ? 'bg-emerald-600 text-white'
                  : 'border-2 border-muted-foreground/35 text-muted-foreground'
              }`}
            >
              {metric.complete ? (
                <Check className="size-5" strokeWidth={3} />
              ) : metric.unavailable ? (
                <span className="text-lg">–</span>
              ) : (
                <span className="size-2.5 rounded-full bg-muted-foreground/35" />
              )}
            </span>
            <p className="mt-3 text-xs font-bold leading-4">{metric.label}</p>
            <p
              className={`mt-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${
                metric.complete
                  ? 'text-emerald-700 dark:text-emerald-300'
                  : 'text-muted-foreground'
              }`}
            >
              {state}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function LoadingCard() {
  return (
    <Card className="border-0 bg-card ring-border">
      <CardContent className="flex min-h-28 items-center justify-center gap-2 text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" /> Loading your private
        plan…
      </CardContent>
    </Card>
  );
}

function DayNavigator({
  selectedDay,
  displayDate,
  viewingToday,
  onSelectDay,
}: {
  selectedDay: string;
  displayDate: string;
  viewingToday: boolean;
  onSelectDay: (day: string) => void;
}) {
  return (
    <div className="mt-3 flex items-center gap-2 rounded-2xl bg-card p-2 shadow-sm ring-1 ring-border">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 rounded-xl"
        aria-label="Show previous day"
        disabled={selectedDay <= LIFE_OS_START_DAY}
        onClick={() =>
          onSelectDay(clampLifeOSDay(shiftDay(selectedDay, -1)))
        }
      >
        <ChevronLeft />
      </Button>
      <label className="relative flex min-w-0 flex-1 items-center gap-2 rounded-xl bg-muted/55 px-3 py-2">
        <CalendarDays className="size-4 shrink-0 text-primary" />
        <span className="sr-only">Choose a date</span>
        <input
          type="date"
          value={selectedDay}
          min={LIFE_OS_START_DAY}
          max={todayKey()}
          aria-label={displayDate}
          className="min-w-0 flex-1 bg-transparent text-sm font-semibold outline-none"
          onChange={(event) =>
            event.target.value && onSelectDay(clampLifeOSDay(event.target.value))
          }
        />
      </label>
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 rounded-xl"
        aria-label={viewingToday ? 'Already showing today' : 'Show next day'}
        disabled={viewingToday}
        onClick={() => onSelectDay(clampLifeOSDay(shiftDay(selectedDay, 1)))}
      >
        <ChevronRight />
      </Button>
    </div>
  );
}

function DatedPageHeader({
  title,
  selectedDay,
  displayDate,
  viewingToday,
  loading,
  onSelectDay,
  onRefresh,
}: {
  title: string;
  selectedDay: string;
  displayDate: string;
  viewingToday: boolean;
  loading: boolean;
  onSelectDay: (day: string) => void;
  onRefresh: () => void;
}) {
  return (
    <>
      <header className="flex items-center justify-between py-4">
        <div>
          <p className="min-h-4 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {displayDate || '\u00a0'}
          </p>
          <h1 className="mt-1 font-heading text-3xl font-semibold tracking-[-0.035em]">
            {title}
          </h1>
        </div>
        <Button
          aria-label={`Refresh ${title.toLowerCase()}`}
          variant="outline"
          size="icon-lg"
          className="shrink-0 rounded-full bg-card"
          onClick={onRefresh}
        >
          <RefreshCw className={loading ? 'animate-spin' : ''} />
        </Button>
      </header>
      <div className="mb-4">
        <DayNavigator
          selectedDay={selectedDay}
          displayDate={displayDate}
          viewingToday={viewingToday}
          onSelectDay={onSelectDay}
        />
      </div>
    </>
  );
}

function AgendaCard({
  sideLabel,
  sideValue,
  sideDetail,
  title,
  description,
  completed = false,
  onClick,
}: {
  sideLabel: string;
  sideValue: string;
  sideDetail?: string;
  title: string;
  description: string;
  completed?: boolean;
  onClick?: () => void;
}) {
  const card = (
    <Card
      size="sm"
      className={`border-0 shadow-sm transition-transform ${completed ? 'bg-emerald-50 ring-emerald-200 dark:bg-emerald-950/30 dark:ring-emerald-800' : 'bg-card/90 ring-border'} ${onClick ? 'active:scale-[.99]' : ''}`}
    >
      <CardContent className="flex items-stretch gap-0 p-0">
        <div
          className={`flex w-[5.25rem] shrink-0 flex-col items-center justify-center border-r px-2 py-4 text-center ${completed ? 'border-emerald-200 dark:border-emerald-800' : 'border-border/70'}`}
        >
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {sideLabel}
          </span>
          <span
            className={`mt-1 text-sm font-bold tabular-nums ${completed ? 'text-emerald-800 dark:text-emerald-300' : 'text-primary'}`}
          >
            {sideValue}
          </span>
          {sideDetail && (
            <span className="mt-0.5 text-[10px] font-medium text-muted-foreground">
              {sideDetail}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1 px-4 py-4">
          <p className="font-heading text-lg font-semibold leading-6">
            {title}
          </p>
          <p className="mt-1.5 whitespace-normal break-words text-sm leading-5 text-muted-foreground">
            {description}
          </p>
        </div>
        {onClick && (
          <ChevronRight className="mr-3 size-4 shrink-0 self-center text-muted-foreground" />
        )}
      </CardContent>
    </Card>
  );
  if (!onClick) return card;
  return (
    <button
      type="button"
      className="block w-full text-left"
      aria-label={`Open ${title}`}
      onClick={onClick}
    >
      {card}
    </button>
  );
}

function NutritionEstimateCard({ analysis }: { analysis: PhotoAnalysis }) {
  const metrics = [
    ['Calories', analysis.estimated_calories, 'kcal'],
    ['Protein', analysis.estimated_protein_g, 'g'],
    ['Carbs', analysis.estimated_carbohydrates_g, 'g'],
    ['Fat', analysis.estimated_fat_g, 'g'],
    ['Fiber', analysis.estimated_fiber_g, 'g'],
    ['Calcium', analysis.estimated_calcium_mg, 'mg'],
  ] as const;
  return (
    <div className="rounded-3xl rounded-tl-lg bg-card p-4 shadow-sm ring-1 ring-border">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">Estimated nutrition</p>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">
          {Math.round(analysis.confidence * 100)}% confidence
        </span>
      </div>
      <p className="mt-2 text-base leading-6">{analysis.summary}</p>
      <div className="mt-4 grid grid-cols-3 gap-x-3 gap-y-4 border-y border-border/70 py-3">
        {metrics.map(([label, value, unit]) => (
          <div key={label}>
            <p className="text-[11px] font-medium text-muted-foreground">
              {label}
            </p>
            <p className="mt-0.5 text-base font-semibold tabular-nums">
              {value == null ? '—' : `${Math.round(value)} ${unit}`}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Estimates change with portions, ingredients, and preparation. Reply with
        a correction before logging.
      </p>
    </div>
  );
}

function briefingInline(text: string): ReactNode[] {
  const tokens = text.split(/(\*\*.*?\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g);
  return tokens.filter(Boolean).map((token, index) => {
    const bold = token.match(/^\*\*(.*?)\*\*$/);
    if (bold) return <strong key={index}>{bold[1]}</strong>;
    const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (link) {
      return (
        <a
          key={index}
          href={link[2]}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-primary underline underline-offset-4"
        >
          {link[1]}
        </a>
      );
    }
    return token;
  });
}

function BriefingBody({ markdown }: { markdown: string }) {
  const withoutTitle = markdown.replace(/^#\s+[^\n]+\n+/, '');
  const blocks = withoutTitle.split(/\n\s*\n/).filter((block) => block.trim());
  return (
    <article className="space-y-5">
      {blocks.map((rawBlock, index) => {
        const block = rawBlock.trim();
        if (block.startsWith('## ')) {
          return (
            <h2
              key={index}
              className="pt-3 font-heading text-2xl font-semibold leading-8 tracking-tight"
            >
              {briefingInline(block.slice(3))}
            </h2>
          );
        }
        if (block.startsWith('### ')) {
          return (
            <h3 key={index} className="pt-2 text-lg font-semibold leading-7">
              {briefingInline(block.slice(4))}
            </h3>
          );
        }
        const lines = block.split('\n');
        if (lines.every((line) => line.trimStart().startsWith('- '))) {
          return (
            <ul key={index} className="list-disc space-y-2 pl-5 text-base leading-7">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{briefingInline(line.trim().slice(2))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="text-base leading-7 text-foreground/90">
            {briefingInline(lines.join(' '))}
          </p>
        );
      })}
    </article>
  );
}

export default function Home() {
  const [view, setView] = useState<View>('today');
  const [themePreference, setThemePreference] =
    useState<ThemePreference>('system');
  const [selectedDay, setSelectedDay] = useState('');
  const [displayDate, setDisplayDate] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [checkIns, setCheckIns] = useState<CheckIn[]>([]);
  const [cycleCheckIns, setCycleCheckIns] = useState<CheckIn[]>([]);
  const [dailyEvents, setDailyEvents] = useState<ProgressEvent[]>([]);
  const [knowledgeRecords, setKnowledgeRecords] = useState<KnowledgeRecord[]>([]);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [whoopStatus, setWhoopStatus] = useState<WhoopStatus>({
    configured: false,
    connected: false,
    scope: [],
    has_refresh_token: false,
  });
  const [whoopBusy, setWhoopBusy] = useState(false);
  const [whoopMessage, setWhoopMessage] = useState('');
  const [briefing, setBriefing] = useState<BriefingDocument | null>(null);
  const [briefingError, setBriefingError] = useState('');
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [briefingAttempt, setBriefingAttempt] = useState(0);
  const [appointmentSync, setAppointmentSync] =
    useState<AppointmentSyncDocument | null>(null);
  const [appointmentSyncError, setAppointmentSyncError] = useState('');
  const [loadingAppointmentSync, setLoadingAppointmentSync] = useState(false);
  const [appointmentSyncAttempt, setAppointmentSyncAttempt] = useState(0);
  const [financeReport, setFinanceReport] =
    useState<FinanceDailyReport | null>(null);
  const [financeAccounts, setFinanceAccounts] = useState<FinanceEmailAccount[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showFullPlan, setShowFullPlan] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [chatDraft, setChatDraft] = useState('');
  const [chatting, setChatting] = useState(false);
  const [checkInResponse, setCheckInResponse] = useState('');
  const [savingCheckIn, setSavingCheckIn] = useState(false);
  const [logConfirmation, setLogConfirmation] =
    useState<LogConfirmation | null>(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const [selectedCheckInId, setSelectedCheckInId] = useState<string | null>(
    null,
  );
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState('');
  const [analyzePhoto, setAnalyzePhoto] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [analyzingNutrition, setAnalyzingNutrition] = useState(false);
  const [photosByCheckIn, setPhotosByCheckIn] = useState<
    Record<string, CheckInPhoto[]>
  >({});
  const [nutritionAnalyses, setNutritionAnalyses] = useState<
    Record<string, PhotoAnalysis>
  >({});
  const [nutritionReviewDraft, setNutritionReviewDraft] =
    useState<NutritionReviewDraft>(EMPTY_NUTRITION_REVIEW_DRAFT);
  const [nutritionTotals, setNutritionTotals] = useState<NutritionTotals>(
    EMPTY_NUTRITION_TOTALS,
  );
  const [nutritionMealSummaries, setNutritionMealSummaries] = useState<string[]>(
    [],
  );
  const [loadingNutritionReview, setLoadingNutritionReview] = useState(false);
  const [nutritionMessages, setNutritionMessages] = useState<
    Record<string, NutritionMessage[]>
  >({});
  const [nutritionDraftImages, setNutritionDraftImages] = useState<
    NutritionDraftImage[]
  >([]);
  const [nutritionComposerFocused, setNutritionComposerFocused] =
    useState(false);
  const [nutritionKeyboardInset, setNutritionKeyboardInset] = useState(0);
  const [hasIOSKeyboardAccessory, setHasIOSKeyboardAccessory] = useState(false);
  const [wellbeingStep, setWellbeingStep] = useState(0);
  const [wellbeingDraft, setWellbeingDraft] = useState<WellbeingDraft>(
    EMPTY_WELLBEING_DRAFT,
  );
  const [meditationSeconds, setMeditationSeconds] = useState(10 * 60);
  const [meditationRunning, setMeditationRunning] = useState(false);
  const [morningAction, setMorningAction] = useState('');
  const [savingWellbeing, setSavingWellbeing] = useState(false);
  const [resumeStateReady, setResumeStateReady] = useState(false);
  const [restoredAgentId, setRestoredAgentId] = useState<string | null>(null);
  const nutritionEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
    const initial: ThemePreference =
      saved === 'light' || saved === 'dark' ? saved : 'system';
    setThemePreference(initial);
    applyThemePreference(initial);

    const colorScheme = window.matchMedia('(prefers-color-scheme: dark)');
    const syncSystemTheme = () => {
      const current = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (!current || current === 'system') applyThemePreference('system');
    };
    colorScheme.addEventListener('change', syncSystemTheme);
    return () => colorScheme.removeEventListener('change', syncSystemTheme);
  }, []);

  const chooseTheme = (preference: ThemePreference) => {
    setThemePreference(preference);
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    applyThemePreference(preference);
  };

  useEffect(() => {
    const saved = readResumeState();
    if (saved) {
      setSelectedDay(clampLifeOSDay(saved.day));
      setView(saved.view);
      setSelectedCheckInId(saved.selectedCheckInId);
      setRestoredAgentId(saved.selectedAgentId);
      setShowFullPlan(Boolean(saved.showFullPlan));
      setCheckInResponse(saved.checkInResponse || '');
      setChatDraft(saved.chatDraft || '');
      setMessages(saved.messages || {});
      setWellbeingStep(Math.min(4, Math.max(0, saved.wellbeingStep || 0)));
      setWellbeingDraft({
        ...EMPTY_WELLBEING_DRAFT,
        ...(saved.wellbeingDraft || {}),
      });
      setMeditationSeconds(
        Math.min(10 * 60, Math.max(0, saved.meditationSeconds ?? 10 * 60)),
      );
      setMeditationRunning(Boolean(saved.meditationRunning));
      setMorningAction(saved.morningAction || '');
      setNutritionMessages(saved.nutritionMessages || {});
      setNutritionAnalyses(saved.nutritionAnalyses || {});
      setNutritionReviewDraft({
        ...EMPTY_NUTRITION_REVIEW_DRAFT,
        ...(saved.nutritionReviewDraft || {}),
      });
      setLogConfirmation(saved.logConfirmation || null);
    } else {
      setSelectedDay(todayKey());
    }
    setResumeStateReady(true);
  }, []);

  const loadDashboard = useCallback(async () => {
    if (!selectedDay) return;
    setLoading(true);
    setError('');
    const { start: startOfDay, end: endOfDay } = dayBounds(selectedDay);
    try {
      const [
        agentData,
        goalData,
        checkInData,
        progressData,
        eventData,
        knowledgeData,
        financeData,
        financeAccountData,
        whoopData,
      ] =
        await Promise.all([
          lifeOS<Agent[]>('/v1/agents'),
          lifeOS<Goal[]>(`/v1/goals?tenant_id=${TENANT_ID}&status=active`),
          lifeOS<CheckIn[]>(
            `/v1/check-ins?tenant_id=${TENANT_ID}&start_at=${encodeURIComponent(startOfDay.toISOString())}&end_at=${encodeURIComponent(endOfDay.toISOString())}&limit=1000`,
          ),
          lifeOS<ProgressSummary>(`/v1/progress?tenant_id=${TENANT_ID}`),
          lifeOS<ProgressEvent[]>(
            `/v1/events?tenant_id=${TENANT_ID}&limit=1000`,
          ),
          lifeOS<KnowledgeRecord[]>(
            `/v1/knowledge-records?tenant_id=${TENANT_ID}&limit=100`,
          ),
          lifeOS<FinanceDailyReport>(
            `/v1/finance/daily/${selectedDay}?tenant_id=${TENANT_ID}`,
          ),
          lifeOS<FinanceEmailAccount[]>(
            `/v1/finance/accounts?tenant_id=${TENANT_ID}`,
          ),
          lifeOS<WhoopStatus>('/v1/integrations/whoop/status'),
        ]);
      const cycleStart = goalData.reduce(
        (earliest, goal) =>
          new Date(goal.start_at).getTime() < earliest.getTime()
            ? new Date(goal.start_at)
            : earliest,
        startOfDay,
      );
      const cycleData = await lifeOS<CheckIn[]>(
        `/v1/check-ins?tenant_id=${TENANT_ID}&start_at=${encodeURIComponent(cycleStart.toISOString())}&end_at=${encodeURIComponent(endOfDay.toISOString())}&limit=1000`,
      );
      const eventsForDay = eventData.filter((event) => {
        const occurredAt = new Date(event.occurred_at).getTime();
        return (
          occurredAt >= startOfDay.getTime() && occurredAt <= endOfDay.getTime()
        );
      });
      setAgents(agentData);
      setGoals(goalData);
      setCheckIns(checkInData);
      setCycleCheckIns(cycleData);
      setDailyEvents(eventsForDay);
      setKnowledgeRecords(knowledgeData);
      setFinanceReport(financeData);
      setFinanceAccounts(financeAccountData);
      setWhoopStatus(whoopData);
      setProgress(progressData);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Life OS is unavailable.',
      );
    } finally {
      setLoading(false);
    }
  }, [selectedDay]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void loadDashboard(), 0);
    return () => window.clearTimeout(timeout);
  }, [loadDashboard]);

  const connectWhoop = async () => {
    setWhoopBusy(true);
    setWhoopMessage('');
    try {
      const authorization = await lifeOS<{ url: string }>(
        '/v1/integrations/whoop/authorize',
        { method: 'POST' },
      );
      window.location.assign(authorization.url);
    } catch (requestError) {
      setWhoopMessage(
        requestError instanceof Error
          ? requestError.message
          : 'WHOOP connection could not begin.',
      );
      setWhoopBusy(false);
    }
  };

  const syncWhoop = useCallback(async () => {
    setWhoopBusy(true);
    setWhoopMessage('');
    try {
      const result = await lifeOS<WhoopSyncResult>(
        `/v1/integrations/whoop/sync?tenant_id=${TENANT_ID}&days=7`,
        { method: 'POST' },
      );
      setWhoopMessage(
        result.created_events
          ? `WHOOP updated ${result.imported_days.length} day${result.imported_days.length === 1 ? '' : 's'}.`
          : 'WHOOP is already up to date.',
      );
      await loadDashboard();
    } catch (requestError) {
      setWhoopMessage(
        requestError instanceof Error
          ? requestError.message
          : 'WHOOP data could not be synced.',
      );
    } finally {
      setWhoopBusy(false);
    }
  }, [loadDashboard]);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get('whoop') !== 'connected') return;
    query.delete('whoop');
    const suffix = query.toString();
    window.history.replaceState(
      {},
      '',
      `${window.location.pathname}${suffix ? `?${suffix}` : ''}`,
    );
    void syncWhoop();
  }, [syncWhoop]);

  const briefingReviewed = dailyEvents.some(
    (event) => event.metric === 'briefing_reviewed' && event.value > 0,
  );

  const markBriefingReviewed = async () => {
    if (!selectedDelivery || briefingReviewed) return;
    try {
      const event = await lifeOS<ProgressEvent>('/v1/events', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: TENANT_ID,
          domain: 'briefing_intern',
          metric: 'briefing_reviewed',
          value: 1,
          unit: 'completion',
          source: 'user_confirmation',
          confidence: 1,
          occurred_at: selectedDelivery.due_at,
          goal_id: selectedDelivery.goal_id,
          metadata: {
            check_in_id: selectedDelivery.id,
            tracked_day: selectedDay,
          },
        }),
      });
      setDailyEvents((current) => [...current, event]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The briefing review could not be saved.',
      );
    }
  };

  useEffect(() => {
    if (!resumeStateReady || !restoredAgentId || !agents.length) return;
    const restoredAgent = agents.find((agent) => agent.id === restoredAgentId);
    if (restoredAgent) setSelectedAgent(restoredAgent);
    setRestoredAgentId(null);
  }, [agents, restoredAgentId, resumeStateReady]);

  const persistResumeState = useCallback(() => {
    if (!resumeStateReady) return;
    const durableNutritionMessages = Object.fromEntries(
      Object.entries(nutritionMessages).map(([checkInId, checkInMessages]) => [
        checkInId,
        checkInMessages.map(
          ({ imagePreviews: _imagePreviews, ...message }) => message,
        ),
      ]),
    );
    const state: ResumeState = {
      day: selectedDay || todayKey(),
      view,
      selectedCheckInId,
      selectedAgentId: selectedAgent?.id || null,
      showFullPlan,
      checkInResponse,
      chatDraft,
      messages,
      wellbeingStep,
      wellbeingDraft,
      meditationSeconds,
      meditationRunning,
      morningAction,
      nutritionMessages: durableNutritionMessages,
      nutritionAnalyses,
      nutritionReviewDraft,
      logConfirmation,
    };
    try {
      window.localStorage.setItem(RESUME_STATE_KEY, JSON.stringify(state));
    } catch {
      // Resume support is best-effort when private browsing blocks storage.
    }
  }, [
    chatDraft,
    checkInResponse,
    logConfirmation,
    meditationRunning,
    meditationSeconds,
    messages,
    morningAction,
    nutritionAnalyses,
    nutritionMessages,
    nutritionReviewDraft,
    resumeStateReady,
    selectedAgent,
    selectedCheckInId,
    selectedDay,
    showFullPlan,
    view,
    wellbeingDraft,
    wellbeingStep,
  ]);

  useEffect(() => {
    if (!resumeStateReady) return;
    const timeout = window.setTimeout(persistResumeState, 150);
    return () => window.clearTimeout(timeout);
  }, [persistResumeState, resumeStateReady]);

  useEffect(() => {
    if (!resumeStateReady) return;
    const saveBeforeSuspension = () => persistResumeState();
    const saveWhenHidden = () => {
      if (document.visibilityState === 'hidden') persistResumeState();
    };
    window.addEventListener('pagehide', saveBeforeSuspension);
    document.addEventListener('visibilitychange', saveWhenHidden);
    return () => {
      window.removeEventListener('pagehide', saveBeforeSuspension);
      document.removeEventListener('visibilitychange', saveWhenHidden);
    };
  }, [persistResumeState, resumeStateReady]);

  const byDeadline = (a: CheckIn, b: CheckIn) =>
    new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
  const allUserCheckIns = checkIns.filter((item) => !isAgentDelivery(item));
  const userCheckIns = allUserCheckIns
    .filter((item) => item.status === 'pending' || item.status === 'delivered')
    .sort(byDeadline);
  const completedCheckIns = allUserCheckIns
    .filter((item) => item.status === 'responded')
    .sort(byDeadline);
  const skippedCheckIns = allUserCheckIns.filter(
    (item) => item.status === 'skipped',
  ).sort(byDeadline);
  const agentDeliveries = checkIns
    .filter((item) => isAgentDelivery(item) && item.status !== 'responded')
    .sort(byDeadline);
  const selectedDelivery = checkIns.find(
    (item) => item.id === selectedCheckInId && isAgentDelivery(item),
  );
  const selectedAppointmentDelivery = checkIns.find(
    (item) =>
      item.id === selectedCheckInId && isAppointmentSyncDelivery(item),
  );
  const activeCheckIn =
    allUserCheckIns.find((item) => item.id === selectedCheckInId) ||
    userCheckIns[0];
  const activePhotos = activeCheckIn
    ? photosByCheckIn[activeCheckIn.id] || []
    : [];
  const activeNutritionAnalysis = activeCheckIn
    ? nutritionAnalyses[activeCheckIn.id] ||
      [...activePhotos].reverse().find((photo) => photo.analysis)?.analysis ||
      null
    : null;
  const activeNutritionMessages = activeCheckIn
    ? nutritionMessages[activeCheckIn.id] || []
    : [];
  const activeCheckInId = activeCheckIn?.id;
  const activeCheckInAgentId = activeCheckIn?.agent_id;
  const activeIsNutritionChat =
    activeCheckInAgentId === 'nutrition_coach' &&
    !isNutritionReview(activeCheckIn);
  const nutritionKeyboardOpen =
    nutritionComposerFocused &&
    (hasIOSKeyboardAccessory || nutritionKeyboardInset > 80);
  const completedCount = completedCheckIns.filter(
    (item) => item.outcome !== 'partial',
  ).length;
  const totalToday =
    userCheckIns.length + completedCheckIns.length + skippedCheckIns.length;
  const dailyPercent = totalToday
    ? Math.round((completedCount / totalToday) * 100)
    : 0;
  const viewingToday = selectedDay === todayKey();

  useEffect(() => {
    if (
      view !== 'briefing' ||
      !selectedDelivery ||
      selectedDelivery.agent_id !== 'briefing_intern'
    ) {
      return;
    }
    let cancelled = false;
    const briefingDay = dayKeyFromInstant(selectedDelivery.due_at);
    setLoadingBriefing(true);
    setBriefingError('');
    void lifeOS<BriefingDocument>(
      `/v1/briefings/${briefingDay}?tenant_id=${TENANT_ID}`,
    )
      .then((document) => {
        if (!cancelled) setBriefing(document);
      })
      .catch(() => {
        if (!cancelled) {
          setBriefing(null);
          setBriefingError(
            'This briefing has not been published to your private Life OS yet.',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingBriefing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [briefingAttempt, selectedDelivery, view]);

  useEffect(() => {
    if (view !== 'appointment-sync' || !selectedAppointmentDelivery) return;
    let cancelled = false;
    const deliveryDay = dayKeyFromInstant(selectedAppointmentDelivery.due_at);
    setLoadingAppointmentSync(true);
    setAppointmentSyncError('');
    void lifeOS<AppointmentSyncDocument>(
      `/v1/appointment-syncs/${deliveryDay}?tenant_id=${TENANT_ID}`,
    )
      .then((document) => {
        if (!cancelled) setAppointmentSync(document);
      })
      .catch(() => {
        if (!cancelled) {
          setAppointmentSync(null);
          setAppointmentSyncError(
            'This appointment-sync report has not been saved to your private Life OS yet.',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingAppointmentSync(false);
      });
    return () => {
      cancelled = true;
    };
  }, [appointmentSyncAttempt, selectedAppointmentDelivery, view]);

  const loadNutritionTotals = useCallback(async () => {
    if (!selectedDay) return;
    setLoadingNutritionReview(true);
    try {
      const events = await lifeOS<ProgressEvent[]>(
        `/v1/events?tenant_id=${TENANT_ID}&limit=1000`,
      );
      const { start, end } = dayBounds(selectedDay);
      const metricKeys: Record<string, keyof NutritionTotals> = {
        nutrition_calories: 'calories',
        nutrition_protein: 'protein',
        nutrition_carbohydrates: 'carbohydrates',
        nutrition_fat: 'fat',
        nutrition_fiber: 'fiber',
        nutrition_calcium: 'calcium',
      };
      const totals = events.reduce<NutritionTotals>(
        (current, event) => {
          const occurredAt = new Date(event.occurred_at).getTime();
          const key = metricKeys[event.metric];
          if (
            key &&
            occurredAt >= start.getTime() &&
            occurredAt <= end.getTime()
          ) {
            current[key] += event.value;
          }
          return current;
        },
        { ...EMPTY_NUTRITION_TOTALS },
      );
      setNutritionTotals(totals);
      const mealSummaries = events
        .filter((event) => {
          const occurredAt = new Date(event.occurred_at).getTime();
          return (
            occurredAt >= start.getTime() &&
            occurredAt <= end.getTime() &&
            event.source === 'mobile_user_confirmation' &&
            typeof event.metadata.nutrition_analysis === 'object' &&
            event.metadata.nutrition_analysis !== null
          );
        })
        .map((event) => {
          const analysis = event.metadata.nutrition_analysis as PhotoAnalysis;
          const checkInId = String(event.metadata.check_in_id || '');
          const title = checkIns.find((item) => item.id === checkInId);
          const occurred = new Date(event.occurred_at);
          const time = `${occurred.getHours()}:${occurred.getMinutes()}`;
          const inferredTitle: Record<string, string> = {
            '11:0': 'Breakfast',
            '12:30': 'Morning Snack',
            '14:0': 'Lunch',
            '20:30': 'Post-workout Protein',
            '21:0': 'Dinner',
            '23:45': 'Late-Night Snack',
          };
          return `${title ? shortTaskTitle(title) : inferredTitle[time] || 'Meal'}: ${analysis.summary}`;
        });
      setNutritionMealSummaries([...new Set(mealSummaries)]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Today’s nutrition totals could not be loaded.',
      );
    } finally {
      setLoadingNutritionReview(false);
    }
  }, [selectedDay]);

  useEffect(() => {
    if (!selectedDay) return;
    setDisplayDate(
      new Intl.DateTimeFormat(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      }).format(localDateFromKey(selectedDay)),
    );
  }, [selectedDay]);

  useEffect(() => {
    if (!resumeStateReady || !isNutritionReview(activeCheckIn)) return;
    const saved = readResumeState();
    if (saved?.selectedCheckInId !== activeCheckInId) {
      setNutritionReviewDraft({ ...EMPTY_NUTRITION_REVIEW_DRAFT });
    }
    void loadNutritionTotals();
  }, [activeCheckInId, loadNutritionTotals, resumeStateReady]);

  useEffect(() => {
    const checkInId = activeCheckInId;
    if (
      !checkInId ||
      (activeCheckInAgentId !== 'nutrition_coach' &&
        activeCheckInAgentId !== 'fitness_coach')
    )
      return;
    let cancelled = false;
    void lifeOS<CheckInPhoto[]>(
      `/v1/check-ins/${checkInId}/photos?tenant_id=${TENANT_ID}`,
    )
      .then((photos) => {
        if (!cancelled) {
          setPhotosByCheckIn((current) => ({
            ...current,
            [checkInId]: photos,
          }));
        }
      })
      .catch(() => {
        // The check-in remains usable if attachment history cannot be loaded.
      });
    return () => {
      cancelled = true;
    };
  }, [activeCheckInId, activeCheckInAgentId]);

  useEffect(
    () => () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview);
    },
    [photoPreview],
  );

  useEffect(() => {
    if (activeCheckInAgentId !== 'nutrition_coach') return;
    nutritionEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, [activeCheckInAgentId, activeNutritionMessages, analyzingNutrition]);

  useEffect(() => {
    if (
      view !== 'check-in' ||
      activeCheckInAgentId !== 'nutrition_coach' ||
      !window.visualViewport
    ) {
      setNutritionKeyboardInset(0);
      return;
    }

    const viewport = window.visualViewport;
    const syncComposerToViewport = () => {
      setNutritionKeyboardInset(
        Math.max(
          0,
          Math.round(window.innerHeight - viewport.height - viewport.offsetTop),
        ),
      );
    };

    syncComposerToViewport();
    viewport.addEventListener('resize', syncComposerToViewport);
    viewport.addEventListener('scroll', syncComposerToViewport);
    window.addEventListener('orientationchange', syncComposerToViewport);

    return () => {
      viewport.removeEventListener('resize', syncComposerToViewport);
      viewport.removeEventListener('scroll', syncComposerToViewport);
      window.removeEventListener('orientationchange', syncComposerToViewport);
    };
  }, [activeCheckInAgentId, view]);

  useEffect(() => {
    const isIOSDevice =
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    setHasIOSKeyboardAccessory(isIOSDevice);
  }, []);

  useEffect(() => {
    if (!resumeStateReady || !activeCheckInId) return;
    const saved = readResumeState();
    const restoringThisRoutine =
      saved?.selectedCheckInId === activeCheckInId &&
      (isWakeUpRoutine(activeCheckIn) || isWindDownRoutine(activeCheckIn));
    if (restoringThisRoutine) {
      const maxStep = isWakeUpRoutine(activeCheckIn) ? 4 : 2;
      setWellbeingStep(
        Math.min(maxStep, Math.max(0, saved.wellbeingStep || 0)),
      );
      setWellbeingDraft({
        ...EMPTY_WELLBEING_DRAFT,
        ...(saved.wellbeingDraft || {}),
      });
      setMeditationSeconds(
        Math.min(10 * 60, Math.max(0, saved.meditationSeconds ?? 10 * 60)),
      );
      setMeditationRunning(Boolean(saved.meditationRunning));
      setMorningAction(saved.morningAction || '');
    } else {
      setWellbeingStep(0);
      setWellbeingDraft({ ...EMPTY_WELLBEING_DRAFT });
      setMeditationSeconds(10 * 60);
      setMeditationRunning(false);
      setMorningAction('');
    }
    if (!isWindDownRoutine(activeCheckIn)) return;
    void lifeOS<ProgressEvent[]>(
      `/v1/events?tenant_id=${TENANT_ID}&metric=mindset_one_action&limit=1`,
    )
      .then((events) => {
        const action = events[0]?.metadata.action;
        if (typeof action === 'string') setMorningAction(action);
      })
      .catch(() => {
        // The evening routine remains usable if the morning action is unavailable.
      });
  }, [activeCheckInId, resumeStateReady]);

  useEffect(() => {
    if (!meditationRunning) return;
    const timer = window.setInterval(() => {
      setMeditationSeconds((current) => {
        if (current <= 1) {
          window.clearInterval(timer);
          setMeditationRunning(false);
          setWellbeingDraft((draft) => ({
            ...draft,
            meditationComplete: true,
          }));
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [meditationRunning]);

  const choosePhoto = (file?: File) => {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      setError('Choose a photo smaller than 12 MB.');
      return;
    }
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
    setError('');
  };

  const uploadPhoto = async (selectedFile?: File) => {
    const file = selectedFile || photoFile;
    if (!activeCheckIn || !file || !supportsPhoto(activeCheckIn)) return;
    const checkInId = activeCheckIn.id;
    const isNutrition = activeCheckIn.agent_id === 'nutrition_coach';
    if (isNutrition) {
      setNutritionMessages((current) => ({
        ...current,
        [checkInId]: [
          ...(current[checkInId] || []),
          { role: 'user', text: 'Meal photo added' },
        ],
      }));
    }
    setUploadingPhoto(true);
    setError('');
    try {
      const photo = await lifeOS<CheckInPhoto>(
        `/v1/check-ins/${checkInId}/photos?tenant_id=${TENANT_ID}&analyze=${isNutrition || analyzePhoto}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': file.type || 'application/octet-stream',
          },
          body: file,
        },
      );
      setPhotosByCheckIn((current) => ({
        ...current,
        [checkInId]: [...(current[checkInId] || []), photo],
      }));
      if (photo.analysis) {
        setNutritionAnalyses((current) => ({
          ...current,
          [checkInId]: photo.analysis as PhotoAnalysis,
        }));
        if (isNutrition) {
          setNutritionMessages((current) => ({
            ...current,
            [checkInId]: [
              ...(current[checkInId] || []),
              {
                role: 'assistant',
                text: photo.analysis?.summary || 'I analyzed your meal photo.',
                analysis: photo.analysis as PhotoAnalysis,
              },
            ],
          }));
        }
      }
      if (photoPreview) URL.revokeObjectURL(photoPreview);
      setPhotoFile(null);
      setPhotoPreview('');
      setAnalyzePhoto(false);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The photo could not be stored.',
      );
    } finally {
      setUploadingPhoto(false);
    }
  };

  const sendNutritionMessage = async () => {
    if (
      !activeCheckIn ||
      activeCheckIn.agent_id !== 'nutrition_coach' ||
      (!checkInResponse.trim() && nutritionDraftImages.length === 0)
    )
      return;
    const checkInId = activeCheckIn.id;
    const message = checkInResponse.trim();
    const draftImages = [...nutritionDraftImages];
    const userText =
      message ||
      `${draftImages.length} meal photo${draftImages.length === 1 ? '' : 's'} added`;
    setNutritionMessages((current) => ({
      ...current,
      [checkInId]: [
        ...(current[checkInId] || []),
        {
          role: 'user',
          text: userText,
          imagePreviews: draftImages.map((image) => image.preview),
        },
      ],
    }));
    setCheckInResponse('');
    setNutritionDraftImages([]);
    setAnalyzingNutrition(true);
    setError('');
    try {
      const priorContext = activeNutritionAnalysis
        ? `Previous estimate: ${activeNutritionAnalysis.summary}. Calories ${activeNutritionAnalysis.estimated_calories ?? 'unknown'} kcal, protein ${activeNutritionAnalysis.estimated_protein_g ?? 'unknown'} g, carbohydrates ${activeNutritionAnalysis.estimated_carbohydrates_g ?? 'unknown'} g, fat ${activeNutritionAnalysis.estimated_fat_g ?? 'unknown'} g, fibre ${activeNutritionAnalysis.estimated_fiber_g ?? 'unknown'} g, calcium ${activeNutritionAnalysis.estimated_calcium_mg ?? 'unknown'} mg. The user now says: ${message || 'Use the newly attached meal photos as additional evidence.'} Re-estimate the meal using this correction or follow-up.`
        : message;
      const images = await Promise.all(
        draftImages.map(async ({ file }) => ({
          media_type: file.type || 'image/jpeg',
          data: await fileToBase64(file),
        })),
      );
      const result = await lifeOS<NutritionConversationResult>(
        `/v1/check-ins/${checkInId}/nutrition-conversation`,
        {
          method: 'POST',
          body: JSON.stringify({
            tenant_id: TENANT_ID,
            description: priorContext,
            images,
          }),
        },
      );
      setNutritionAnalyses((current) => ({
        ...current,
        [checkInId]: result.analysis,
      }));
      setPhotosByCheckIn((current) => ({
        ...current,
        [checkInId]: [...(current[checkInId] || []), ...result.photos],
      }));
      setNutritionMessages((current) => ({
        ...current,
        [checkInId]: [
          ...(current[checkInId] || []),
          {
            role: 'assistant',
            text: result.analysis.summary,
            analysis: result.analysis,
          },
        ],
      }));
    } catch (requestError) {
      setNutritionMessages((current) => ({
        ...current,
        [checkInId]: (current[checkInId] || []).slice(0, -1),
      }));
      setCheckInResponse(message);
      setNutritionDraftImages(draftImages);
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The meal could not be analyzed.',
      );
    } finally {
      setAnalyzingNutrition(false);
    }
  };

  const submitCheckIn = async (
    outcome: 'done' | 'partial' | 'skipped',
    responseOverride?: string,
  ) => {
    if (!activeCheckIn) return;
    setSavingCheckIn(true);
    setError('');
    try {
      if (outcome !== 'skipped') {
        await lifeOS('/v1/events', {
          method: 'POST',
          body: JSON.stringify({
            tenant_id: TENANT_ID,
            domain: activeCheckIn.agent_id,
            metric: `check_in_${activeCheckIn.prompt_id}`,
            value: outcome === 'done' ? 1 : 0.5,
            unit: 'completion',
            source: 'mobile_user_confirmation',
            confidence: 1,
            occurred_at: activeCheckIn.due_at,
            goal_id: activeCheckIn.goal_id,
            metadata: {
              check_in_id: activeCheckIn.id,
              tracked_day: selectedDay,
              logged_at: new Date().toISOString(),
              outcome,
              response:
                activeCheckIn.agent_id === 'nutrition_coach' &&
                !isNutritionReview(activeCheckIn)
                  ? activeNutritionMessages
                      .filter((message) => message.role === 'user')
                      .map((message) => message.text)
                      .join('\n')
                  : (responseOverride ?? checkInResponse.trim()),
              photo_ids: activePhotos.map((photo) => photo.id),
              nutrition_analysis:
                activeCheckIn.agent_id === 'nutrition_coach' &&
                !isNutritionReview(activeCheckIn)
                  ? activeNutritionAnalysis
                  : null,
              nutrition_conversation:
                activeCheckIn.agent_id === 'nutrition_coach' &&
                !isNutritionReview(activeCheckIn)
                  ? activeNutritionMessages.map((message) => ({
                      role: message.role,
                      text: message.text,
                    }))
                  : null,
            },
          }),
        });
        if (
          activeCheckIn.agent_id === 'nutrition_coach' &&
          !isNutritionReview(activeCheckIn) &&
          activeNutritionAnalysis
        ) {
          const nutritionMetrics = [
            [
              'nutrition_calories',
              activeNutritionAnalysis.estimated_calories,
              'kcal',
            ],
            [
              'nutrition_protein',
              activeNutritionAnalysis.estimated_protein_g,
              'g',
            ],
            [
              'nutrition_carbohydrates',
              activeNutritionAnalysis.estimated_carbohydrates_g,
              'g',
            ],
            ['nutrition_fat', activeNutritionAnalysis.estimated_fat_g, 'g'],
            [
              'nutrition_fiber',
              activeNutritionAnalysis.estimated_fiber_g,
              'g',
            ],
            [
              'nutrition_calcium',
              activeNutritionAnalysis.estimated_calcium_mg,
              'mg',
            ],
          ] as const;
          await Promise.all(
            nutritionMetrics
              .filter(([, value]) => value != null)
              .map(([metric, value, unit]) =>
                lifeOS('/v1/events', {
                  method: 'POST',
                  body: JSON.stringify({
                    tenant_id: TENANT_ID,
                    domain: 'nutrition',
                    metric,
                    value,
                    unit,
                    source: 'nutrition_coach_estimate',
                    confidence: activeNutritionAnalysis.confidence,
                    occurred_at: activeCheckIn.due_at,
                    goal_id: activeCheckIn.goal_id,
                    metadata: {
                      check_in_id: activeCheckIn.id,
                      tracked_day: selectedDay,
                      logged_at: new Date().toISOString(),
                      estimated: true,
                    },
                  }),
                }),
              ),
          );
        }
      }
      const updatedCheckIn = await lifeOS<CheckIn>(
        `/v1/check-ins/${activeCheckIn.id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            tenant_id: TENANT_ID,
            status: outcome === 'skipped' ? 'skipped' : 'responded',
            outcome: outcome === 'skipped' ? null : outcome,
          }),
        },
      );
      const updatedProgress = await lifeOS<ProgressSummary>(
        `/v1/progress?tenant_id=${TENANT_ID}`,
      );
      const taskTitle = shortTaskTitle(activeCheckIn);
      setLogConfirmation({
        title: outcome === 'skipped' ? 'Task skipped' : 'Action logged',
        message:
          outcome === 'skipped'
            ? `${taskTitle} has been skipped for ${viewingToday ? 'today' : displayDate}.`
            : outcome === 'partial'
              ? `${taskTitle} has been logged as partially complete.`
              : `${taskTitle} has been logged as complete.`,
        updatedCheckIn,
        updatedProgress,
        hasNextTask: userCheckIns.some((item) => item.id !== activeCheckIn.id),
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Your response could not be saved.',
      );
    } finally {
      setSavingCheckIn(false);
    }
  };

  const saveWellbeingRoutine = async () => {
    if (!activeCheckIn) return;
    const morning = isWakeUpRoutine(activeCheckIn);
    const routineEvents = morning
      ? [
          {
            metric: 'mindset_accomplishments',
            value: 1,
            unit: 'entry',
            metadata: { entry: wellbeingDraft.accomplishments },
          },
          {
            metric: 'mindset_gratitude',
            value: 1,
            unit: 'entry',
            metadata: { entry: wellbeingDraft.gratitude },
          },
          {
            metric: 'mindset_affirmations',
            value: 1,
            unit: 'recitation',
            metadata: { routine: 'wake_up' },
          },
          {
            metric: 'mindset_meditation_minutes',
            value: 10,
            unit: 'minutes',
            metadata: { completed: true },
          },
          {
            metric: 'mindset_one_action',
            value: 1,
            unit: 'entry',
            metadata: { action: wellbeingDraft.oneAction },
          },
        ]
      : [
          {
            metric: 'mindset_emotional_dump',
            value: 1,
            unit: 'entry',
            metadata: { entry: wellbeingDraft.emotionalDump },
          },
          {
            metric: 'mindset_one_action_follow_through',
            value: wellbeingDraft.actionCompleted ? 1 : 0,
            unit: 'completion',
            metadata: {
              planned_action: morningAction,
              completed: wellbeingDraft.actionCompleted,
            },
          },
          {
            metric: 'mindset_affirmations',
            value: 1,
            unit: 'recitation',
            metadata: { routine: 'wind_down' },
          },
        ];
    setSavingWellbeing(true);
    setError('');
    try {
      await Promise.all(
        routineEvents.map((event) =>
          lifeOS('/v1/events', {
            method: 'POST',
            body: JSON.stringify({
              tenant_id: TENANT_ID,
              domain: 'inner_wellbeing',
              source: 'guided_wellbeing_routine',
              confidence: 1,
              occurred_at: activeCheckIn.due_at,
              goal_id: activeCheckIn.goal_id,
              ...event,
              metadata: {
                ...event.metadata,
                check_in_id: activeCheckIn.id,
                tracked_day: selectedDay,
                logged_at: new Date().toISOString(),
              },
            }),
          }),
        ),
      );
      const summary = morning
        ? `Accomplishments: ${wellbeingDraft.accomplishments}\nGratitude: ${wellbeingDraft.gratitude}\nOne action: ${wellbeingDraft.oneAction}`
        : `Emotional dump completed. Planned action completed: ${wellbeingDraft.actionCompleted ? 'yes' : 'no'}.`;
      await submitCheckIn('done', summary);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Your wellbeing routine could not be saved.',
      );
    } finally {
      setSavingWellbeing(false);
    }
  };

  const saveNutritionReview = async () => {
    if (
      !activeCheckIn ||
      !nutritionReviewDraft.hunger ||
      !nutritionReviewDraft.energy ||
      !nutritionReviewDraft.breastfeeding
    )
      return;
    const hungerSeverity = {
      comfortable: 0,
      hungrier: 1,
      persistent: 2,
    }[nutritionReviewDraft.hunger];
    const energySeverity = {
      steady: 0,
      low: 1,
      weak_dizzy: 2,
    }[nutritionReviewDraft.energy];
    const breastfeedingSeverity = {
      none: 0,
      other: 1,
      reduced_supply: 2,
    }[nutritionReviewDraft.breastfeeding];
    const reviewEvents = [
      {
        metric: 'nutrition_hunger_check',
        value: hungerSeverity,
        category: nutritionReviewDraft.hunger,
      },
      {
        metric: 'nutrition_energy_check',
        value: energySeverity,
        category: nutritionReviewDraft.energy,
      },
      {
        metric: 'nutrition_breastfeeding_check',
        value: breastfeedingSeverity,
        category: nutritionReviewDraft.breastfeeding,
      },
    ];
    setSavingCheckIn(true);
    setError('');
    try {
      await Promise.all(
        reviewEvents.map((event) =>
          lifeOS('/v1/events', {
            method: 'POST',
            body: JSON.stringify({
              tenant_id: TENANT_ID,
              domain: 'nutrition',
              metric: event.metric,
              value: event.value,
              unit: 'severity',
              source: 'nutrition_coach_daily_review',
              confidence: 1,
              occurred_at: activeCheckIn.due_at,
              goal_id: activeCheckIn.goal_id,
              metadata: {
                check_in_id: activeCheckIn.id,
                tracked_day: selectedDay,
                logged_at: new Date().toISOString(),
                category: event.category,
                flagged: event.value > 0,
                nutrition_totals: nutritionTotals,
              },
            }),
          }),
        ),
      );
      const summary = [
        `Calories: ${Math.round(nutritionTotals.calories)} kcal`,
        `Protein: ${Math.round(nutritionTotals.protein)} g`,
        `Carbohydrates: ${Math.round(nutritionTotals.carbohydrates)} g`,
        `Fat: ${Math.round(nutritionTotals.fat)} g`,
        `Fiber: ${Math.round(nutritionTotals.fiber)} g`,
        `Calcium: ${Math.round(nutritionTotals.calcium)} mg`,
        `Hunger: ${nutritionReviewDraft.hunger}`,
        `Energy: ${nutritionReviewDraft.energy}`,
        `Breastfeeding: ${nutritionReviewDraft.breastfeeding}`,
        `Coach conversation: ${activeNutritionMessages.map((message) => `${message.role}: ${message.text}`).join(' | ')}`,
      ].join('\n');
      await submitCheckIn('done', summary);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Your daily nutrition review could not be saved.',
      );
      setSavingCheckIn(false);
    }
  };

  const sendNutritionReviewMessage = async (startConversation = false) => {
    if (!activeCheckIn || !isNutritionReview(activeCheckIn) || chatting) return;
    const message = startConversation
      ? `Hunger: ${nutritionReviewDraft.hunger}; energy: ${nutritionReviewDraft.energy}; breastfeeding concern: ${nutritionReviewDraft.breastfeeding}.`
      : checkInResponse.trim();
    if (!message) return;
    const checkInId = activeCheckIn.id;
    setNutritionMessages((current) => ({
      ...current,
      [checkInId]: [
        ...(current[checkInId] || []),
        { role: 'user', text: message },
      ],
    }));
    setCheckInResponse('');
    setChatting(true);
    setError('');
    const nutritionGoal = goals.find(
      (goal) => goal.owner_agent === 'nutrition_coach',
    );
    const target = (key: string) =>
      nutritionGoal?.metrics.find((metric) => metric.key === key)
        ?.target_value ?? 'not set';
    const transcript = [...activeNutritionMessages, { role: 'user', text: message }]
      .map((item) => `${item.role}: ${item.text}`)
      .join('\n');
    const coachingRequest = `
This is the user's daily nutrition reflection for ${displayDate}.

Meals already logged:
${nutritionMealSummaries.length ? nutritionMealSummaries.map((meal) => `- ${meal}`).join('\n') : '- No meal descriptions were available; do not invent them.'}

Estimated totals and approved daily targets:
- Calories: ${Math.round(nutritionTotals.calories)} / ${target('daily_calories')} kcal
- Protein: ${Math.round(nutritionTotals.protein)} / ${target('daily_protein')} g
- Carbohydrates: ${Math.round(nutritionTotals.carbohydrates)} / ${target('daily_carbohydrates')} g
- Fat: ${Math.round(nutritionTotals.fat)} / ${target('daily_fat')} g
- Fiber: ${Math.round(nutritionTotals.fiber)} / ${target('daily_fiber')} g
- Calcium: ${Math.round(nutritionTotals.calcium)} / ${target('daily_calcium')} mg

Conversation so far:
${transcript}

Respond as the Nutrition Coach in a warm, concise conversation. Reflect what the
user ate and how they felt. Distinguish estimates from facts. Ask at most one useful
follow-up question. Suggest one to three small, specific food or timing changes for
tomorrow that support the approved targets and breastfeeding; do not recommend
restricting intake or diagnose a condition. If the reported symptoms are concerning
or persistent, advise contacting a clinician or lactation professional.`;
    try {
      const reply = await lifeOS<AgentReply>('/v1/chat', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: TENANT_ID,
          agent_id: 'nutrition_coach',
          message: coachingRequest,
        }),
      });
      const responseText = [reply.summary, ...reply.questions, ...reply.warnings]
        .filter(Boolean)
        .join('\n\n');
      setNutritionMessages((current) => ({
        ...current,
        [checkInId]: [
          ...(current[checkInId] || []),
          { role: 'assistant', text: responseText },
        ],
      }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The Nutrition Coach could not respond.',
      );
    } finally {
      setChatting(false);
    }
  };

  const closeLogConfirmation = (destination: 'next' | 'today') => {
    if (!logConfirmation) return;
    setCheckIns((current) =>
      current.map((item) =>
        item.id === logConfirmation.updatedCheckIn.id
          ? logConfirmation.updatedCheckIn
          : item,
      ),
    );
    setProgress(logConfirmation.updatedProgress);
    setSelectedCheckInId(null);
    setCheckInResponse('');
    setNutritionComposerFocused(false);
    setLogConfirmation(null);
    if (destination === 'today') setView('today');
  };

  const sendChat = async () => {
    const message = chatDraft.trim();
    if (!selectedAgent || !message || chatting) return;
    const agentId = selectedAgent.id;
    setMessages((current) => ({
      ...current,
      [agentId]: [...(current[agentId] || []), { role: 'user', text: message }],
    }));
    setChatDraft('');
    setChatting(true);
    setError('');
    try {
      const reply = await lifeOS<AgentReply>('/v1/chat', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: TENANT_ID,
          agent_id: agentId,
          message,
        }),
      });
      const responseText = [
        reply.summary,
        ...reply.questions,
        ...reply.warnings,
      ]
        .filter(Boolean)
        .join('\n\n');
      setMessages((current) => ({
        ...current,
        [agentId]: [
          ...(current[agentId] || []),
          { role: 'assistant', text: responseText },
        ],
      }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The agent could not respond.',
      );
    } finally {
      setChatting(false);
    }
  };

  const renderToday = () => (
    <>
      <DatedPageHeader
        title="Your Plan for the Day"
        selectedDay={selectedDay}
        displayDate={displayDate}
        viewingToday={viewingToday}
        loading={loading}
        onSelectDay={(day) => {
          setSelectedCheckInId(null);
          setSelectedDay(day);
        }}
        onRefresh={() => void loadDashboard()}
      />

      {!viewingToday && (
        <div className="mb-4 flex items-center justify-between rounded-2xl bg-amber-50 px-4 py-3 text-amber-950 ring-1 ring-amber-200 dark:bg-amber-950/25 dark:text-amber-100 dark:ring-amber-900">
          <p className="text-sm leading-5">
            Viewing a past day. Unfinished tasks can still be updated.
          </p>
          <Button
            variant="ghost"
            className="ml-2 h-9 shrink-0 rounded-xl px-3 text-amber-950 dark:text-amber-100"
            onClick={() => {
              setSelectedCheckInId(null);
              setSelectedDay(todayKey());
            }}
          >
            Today
          </Button>
        </div>
      )}

      <Card className="mt-3 border-0 bg-primary text-primary-foreground shadow-[0_18px_50px_-25px_var(--shadow-color)] ring-0">
        <CardHeader>
          <CardDescription className="text-primary-foreground/70">
            Chief of Staff
          </CardDescription>
          <CardTitle className="text-xl font-semibold">
            {userCheckIns.length
              ? `${userCheckIns.length} check-ins are on ${viewingToday ? 'today’s' : 'this day’s'} plan.`
              : `You are caught up for ${viewingToday ? 'today' : 'this day'}.`}
          </CardTitle>
          <CardAction>
            <span className="inline-flex size-10 items-center justify-center rounded-full bg-white/12">
              <Sparkles className="size-5" />
            </span>
          </CardAction>
        </CardHeader>
        <CardContent>
          <p className="max-w-[32ch] text-sm leading-6 text-primary-foreground/80">
            {goals.length
              ? `Your plan is grounded in ${goals.length} active Goal Contract${goals.length === 1 ? '' : 's'}.`
              : 'Approve Goal Contracts to let your team build a precise daily plan.'}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button
              className="h-11 rounded-full bg-white px-5 text-primary hover:bg-white/90"
              size="lg"
              onClick={() => setShowFullPlan((value) => !value)}
            >
              {showFullPlan ? 'Show priorities' : 'Show complete plan'}{' '}
              <ChevronRight />
            </Button>
          </div>
        </CardContent>
      </Card>

      <section className="mt-7" aria-labelledby="today-heading">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground">
              {completedCount} completed · {userCheckIns.length} remaining
            </p>
            <h2
              id="today-heading"
              className="font-heading text-xl font-semibold tracking-tight"
            >
              {showFullPlan ? 'Complete plan' : 'Next priorities'}
            </h2>
          </div>
          <span className="text-sm font-semibold text-primary">
            {dailyPercent}%
          </span>
        </div>
        <Progress value={dailyPercent} className="mb-5" />

        {loading ? (
          <LoadingCard />
        ) : error && !userCheckIns.length && !agentDeliveries.length ? (
          <ConnectionCard onRetry={loadDashboard} />
        ) : userCheckIns.length ? (
          <div className="space-y-3">
            {userCheckIns
              .slice(0, showFullPlan ? userCheckIns.length : 4)
              .map((item) => {
                const goal = goals.find((goal) => goal.id === item.goal_id);
                return (
                  <AgendaCard
                    key={item.id}
                    sideLabel="By"
                    sideValue={deliveryTime(item.due_at)}
                    title={shortTaskTitle(item)}
                    description={boundedDescription(
                      compactTaskScope(item, goal),
                    )}
                    onClick={() => {
                      setSelectedCheckInId(item.id);
                      setView('check-in');
                    }}
                  />
                );
              })}
          </div>
        ) : (
          <Card className="border-0 bg-card ring-border">
            <CardContent className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-full bg-success text-white">
                <Check />
              </span>
              <div>
                <p className="font-semibold">Nothing else is due.</p>
                <p className="text-sm text-muted-foreground">
                  {viewingToday
                    ? 'Enjoy the space you created.'
                    : 'There are no unfinished tasks on this date.'}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </section>

      {agentDeliveries.length > 0 && (
        <section className="mt-7" aria-labelledby="agent-deliveries-heading">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Automatic · no input needed
          </p>
          <h2
            id="agent-deliveries-heading"
            className="mt-1 font-heading text-lg font-semibold"
          >
            Your team’s deliveries
          </h2>
          <div className="mt-3 space-y-3">
            {agentDeliveries.map((item) => {
              const goal = goals.find((goal) => goal.id === item.goal_id);
              return (
                <AgendaCard
                  key={item.id}
                  sideLabel="Receive"
                  sideValue={deliveryTime(item.due_at)}
                  title={shortTaskTitle(item)}
                  description={deliveryDescription(item, goal)}
                  onClick={
                    item.agent_id === 'briefing_intern'
                      ? () => {
                          setSelectedCheckInId(item.id);
                          setBriefing(null);
                          setView('briefing');
                        }
                      : isAppointmentSyncDelivery(item)
                        ? () => {
                            setSelectedCheckInId(item.id);
                            setAppointmentSync(null);
                            setView('appointment-sync');
                          }
                        : isFinanceDelivery(item)
                          ? () => {
                              setSelectedCheckInId(item.id);
                              setView('finance');
                            }
                      : undefined
                  }
                />
              );
            })}
          </div>
        </section>
      )}

      {completedCheckIns.length > 0 && (
        <section className="mt-7" aria-labelledby="completed-heading">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 text-left"
            aria-expanded={showCompleted}
            onClick={() => setShowCompleted((value) => !value)}
          >
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                History
              </p>
              <h2
                id="completed-heading"
                className="mt-1 font-heading text-lg font-semibold"
              >
                Completed ({completedCheckIns.length})
              </h2>
            </div>
            <ChevronDown
              className={`size-5 text-muted-foreground transition-transform ${showCompleted ? 'rotate-180' : ''}`}
            />
          </button>
          {showCompleted && (
            <div className="mt-3 space-y-3">
              {completedCheckIns.map((item) => {
                const goal = goals.find((goal) => goal.id === item.goal_id);
                const isPartial = item.outcome === 'partial';
                const timing = !item.completed_at
                  ? 'Completed'
                  : completedOnTime(item)
                    ? 'On time'
                    : 'Late';
                return (
                  <AgendaCard
                    key={item.id}
                    sideLabel={isPartial ? 'Status' : 'Completed'}
                    sideValue={isPartial ? 'Partial' : timing}
                    sideDetail={
                      item.completed_at
                        ? deliveryTime(item.completed_at)
                        : undefined
                    }
                    title={shortTaskTitle(item)}
                    description={boundedDescription(
                      compactTaskScope(item, goal),
                    )}
                    completed={!isPartial}
                  />
                );
              })}
            </div>
          )}
        </section>
      )}

      {skippedCheckIns.length > 0 && (
        <section className="mt-5" aria-labelledby="skipped-heading">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              History
            </p>
            <h2
              id="skipped-heading"
              className="mt-1 font-heading text-lg font-semibold"
            >
              Skipped ({skippedCheckIns.length})
            </h2>
          </div>
          <div className="mt-3 space-y-3">
            {skippedCheckIns.map((item) => {
              const goal = goals.find((goal) => goal.id === item.goal_id);
              return (
                <AgendaCard
                  key={item.id}
                  sideLabel="Status"
                  sideValue="Skipped"
                  title={shortTaskTitle(item)}
                  description={boundedDescription(compactTaskScope(item, goal))}
                  onClick={() => {
                    setSelectedCheckInId(item.id);
                    setView('check-in');
                  }}
                />
              );
            })}
          </div>
        </section>
      )}

      <section className="mt-7">
        <h2 className="font-heading text-lg font-semibold">Quick access</h2>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            aria-label="Ask the Chief of Staff"
            onClick={() => {
              const chief = agents.find(
                (agent) => agent.id === 'chief_of_staff',
              );
              if (chief) {
                setSelectedAgent(chief);
                setView('agents');
              }
            }}
            className="text-left"
          >
            <Card size="sm" className="h-full border-0 bg-card ring-border">
              <CardContent>
                <MessageCircle className="mb-3 size-5 text-primary" />
                <p className="font-semibold">Ask Chief of Staff</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Replan or resolve a conflict
                </p>
              </CardContent>
            </Card>
          </button>
          <button
            aria-label="See progress"
            onClick={() => setView('progress')}
            className="text-left"
          >
            <Card size="sm" className="h-full border-0 bg-card ring-border">
              <CardContent>
                <BarChart3 className="mb-3 size-5 text-primary" />
                <p className="font-semibold">See progress</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Only confirmed outcomes
                </p>
              </CardContent>
            </Card>
          </button>
        </div>
      </section>
    </>
  );

  const renderNutritionCheckIn = (checkIn: CheckIn) => {
    const plannedMeal = compactTaskScope(
      checkIn,
      goals.find((goal) => goal.id === checkIn.goal_id),
    );
    return (
      <div className="min-h-dvh bg-background">
        <header className="sticky top-0 z-30 border-b border-border/70 bg-background/95 px-4 pb-3 pt-[max(.75rem,env(safe-area-inset-top))] backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <Button
              size="icon-lg"
              variant="ghost"
              className="rounded-full"
              aria-label="Back to selected day"
              onClick={() => setView('today')}
            >
              <ArrowLeft />
            </Button>
            <AgentMark agentId="nutrition_coach" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-orange-800 dark:text-orange-300">
                Nutrition Coach
              </p>
              <h1 className="truncate font-heading text-xl font-semibold">
                {shortTaskTitle(checkIn)}
              </h1>
            </div>
          </div>
          <p className="mt-3 rounded-2xl bg-muted/70 px-3.5 py-2.5 text-sm leading-5 text-muted-foreground">
            <span className="font-semibold text-foreground">Planned: </span>
            {plannedMeal}
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mx-4 mt-3 rounded-2xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <section
          className={`space-y-5 px-4 pt-5 ${nutritionDraftImages.length ? 'pb-[15rem]' : nutritionKeyboardOpen ? 'pb-[7.5rem]' : 'pb-[11rem]'}`}
          aria-label="Nutrition Coach conversation"
        >
          {activeNutritionMessages.length === 0 && !activeNutritionAnalysis && (
            <div className="max-w-[92%] rounded-3xl rounded-tl-lg bg-card px-4 py-3.5 text-base leading-6 shadow-sm ring-1 ring-border">
              Tell me what you ate. Add text, up to five photos, or both in one
              message. I’ll estimate calories, macros, fiber, and calcium for the meal
              as a whole.
            </div>
          )}
          {activeNutritionMessages.length === 0 && activeNutritionAnalysis && (
            <NutritionEstimateCard analysis={activeNutritionAnalysis} />
          )}
          {activeNutritionMessages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.analysis ? (
                <div className="w-full">
                  <NutritionEstimateCard analysis={message.analysis} />
                </div>
              ) : (
                <div
                  className={`max-w-[92%] overflow-hidden rounded-3xl text-base leading-6 ${message.role === 'user' ? 'rounded-tr-lg bg-primary text-primary-foreground' : 'rounded-tl-lg bg-card shadow-sm ring-1 ring-border'}`}
                >
                  {message.imagePreviews?.length ? (
                    <div
                      className={`grid gap-1 p-1 ${message.imagePreviews.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}
                    >
                      {message.imagePreviews.map((preview, imageIndex) => (
                        <Image
                          key={`${preview}-${imageIndex}`}
                          src={preview}
                          alt={`Meal attachment ${imageIndex + 1}`}
                          width={480}
                          height={360}
                          unoptimized
                          className="aspect-square w-full rounded-2xl object-cover"
                        />
                      ))}
                    </div>
                  ) : null}
                  {message.text && (
                    <p className="whitespace-pre-wrap px-4 py-3">
                      {message.text}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
          {analyzingNutrition && (
            <div className="flex justify-start">
              <div className="inline-flex items-center gap-2 rounded-3xl rounded-tl-lg bg-card px-4 py-3 text-sm shadow-sm ring-1 ring-border">
                <LoaderCircle className="size-4 animate-spin" /> Analyzing the
                complete meal…
              </div>
            </div>
          )}
          <div ref={nutritionEndRef} />
        </section>

        <div
          className="fixed inset-x-0 z-50 mx-auto w-full max-w-md bg-gradient-to-t from-background via-background to-transparent px-3 pb-[max(.65rem,env(safe-area-inset-bottom))] pt-5"
          style={{
            bottom: `${nutritionKeyboardInset + (nutritionComposerFocused && hasIOSKeyboardAccessory ? 92 : 0)}px`,
          }}
        >
          <div className="rounded-[2rem] bg-card px-2.5 pb-2.5 pt-2 shadow-[0_8px_32px_-12px_var(--shadow-color)] ring-1 ring-border">
            {nutritionDraftImages.length > 0 && (
              <div className="flex gap-2 overflow-x-auto px-1 pb-1 pt-1">
                {nutritionDraftImages.map((image, index) => (
                  <div key={image.preview} className="relative shrink-0">
                    <Image
                      src={image.preview}
                      alt={`Selected meal photo ${index + 1}`}
                      width={96}
                      height={96}
                      unoptimized
                      className="size-16 rounded-xl object-cover ring-1 ring-border"
                    />
                    <button
                      type="button"
                      className="absolute -right-1 -top-1 flex size-6 items-center justify-center rounded-full bg-foreground text-background shadow"
                      aria-label={`Remove photo ${index + 1}`}
                      onClick={() => {
                        URL.revokeObjectURL(image.preview);
                        setNutritionDraftImages((current) =>
                          current.filter(
                            (item) => item.preview !== image.preview,
                          ),
                        );
                      }}
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
                <span className="self-center whitespace-nowrap pr-1 text-xs font-medium text-muted-foreground">
                  {nutritionDraftImages.length}/5 photos
                </span>
              </div>
            )}
            <Textarea
              value={checkInResponse}
              onChange={(event) => setCheckInResponse(event.target.value)}
              onFocus={() => setNutritionComposerFocused(true)}
              onBlur={() => setNutritionComposerFocused(false)}
              placeholder="Describe the meal or add a correction…"
              className="max-h-32 min-h-14 resize-none border-0 bg-transparent px-3 py-2 text-base shadow-none focus-visible:ring-0"
              disabled={analyzingNutrition}
            />
            <div className="flex items-center justify-between px-1">
              <label
                className={`flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-primary hover:bg-muted active:scale-[.98] ${nutritionDraftImages.length >= 5 || analyzingNutrition ? 'pointer-events-none opacity-40' : ''}`}
                aria-label="Add up to five meal photos"
              >
                <Camera className="size-5" />
                <input
                  className="sr-only"
                  type="file"
                  accept="image/*"
                  multiple
                  disabled={
                    nutritionDraftImages.length >= 5 || analyzingNutrition
                  }
                  onChange={(event) => {
                    const selected = Array.from(event.target.files || []);
                    const remaining = 5 - nutritionDraftImages.length;
                    const accepted = selected
                      .filter((file) => file.size <= 12 * 1024 * 1024)
                      .slice(0, remaining)
                      .map((file) => ({
                        file,
                        preview: URL.createObjectURL(file),
                      }));
                    if (selected.some((file) => file.size > 12 * 1024 * 1024)) {
                      setError('Each photo must be smaller than 12 MB.');
                    } else if (selected.length > remaining) {
                      setError('You can attach up to five photos per message.');
                    } else {
                      setError('');
                    }
                    setNutritionDraftImages((current) => [
                      ...current,
                      ...accepted,
                    ]);
                    event.currentTarget.value = '';
                  }}
                />
              </label>
              <Button
                size="icon"
                className="size-11 shrink-0 rounded-full"
                aria-label="Send meal message"
                disabled={
                  (!checkInResponse.trim() &&
                    nutritionDraftImages.length === 0) ||
                  analyzingNutrition
                }
                onPointerDown={(event) => event.preventDefault()}
                onClick={() => void sendNutritionMessage()}
              >
                {analyzingNutrition ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Send />
                )}
              </Button>
            </div>
          </div>

          {!nutritionKeyboardOpen && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Button
                className="h-10 rounded-xl"
                disabled={!activeNutritionAnalysis || savingCheckIn}
                onClick={() => void submitCheckIn('done')}
              >
                <Check /> Log this
              </Button>
              <Button
                className="h-10 rounded-xl"
                variant="ghost"
                disabled={savingCheckIn}
                onClick={() => void submitCheckIn('skipped')}
              >
                {viewingToday ? 'Skip today' : 'Skip this day'}
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderNutritionReview = (checkIn: CheckIn) => {
    const hasNutritionTotals = Object.values(nutritionTotals).some(
      (value) => value > 0,
    );
    const reviewComplete = Boolean(
      nutritionReviewDraft.hunger &&
      nutritionReviewDraft.energy &&
      nutritionReviewDraft.breastfeeding,
    );
    const hasCoachReply = activeNutritionMessages.some(
      (message) => message.role === 'assistant',
    );
    const hasSafetyFlag =
      nutritionReviewDraft.hunger === 'persistent' ||
      nutritionReviewDraft.energy === 'weak_dizzy' ||
      (nutritionReviewDraft.breastfeeding !== null &&
        nutritionReviewDraft.breastfeeding !== 'none');
    const totals = [
      ['Calories', nutritionTotals.calories, 'kcal'],
      ['Protein', nutritionTotals.protein, 'g'],
      ['Carbs', nutritionTotals.carbohydrates, 'g'],
      ['Fat', nutritionTotals.fat, 'g'],
      ['Fiber', nutritionTotals.fiber, 'g'],
      ['Calcium', nutritionTotals.calcium, 'mg'],
    ] as const;

    return (
      <>
        <PageHeader
          title="Daily Nutrition Reflection"
          subtitle="Nutrition Coach"
        />
        <Card className="mt-3 border-0 bg-card shadow-sm ring-border">
          <CardHeader>
            <CardTitle className="text-xl">
              {viewingToday ? 'Today’s nutrition' : 'Nutrition for this day'}
            </CardTitle>
            <CardDescription className="leading-5">
              Calculated automatically from meals logged for {displayDate}.
            </CardDescription>
            <CardAction>
              <Button
                size="icon"
                variant="ghost"
                className="rounded-full"
                aria-label="Refresh nutrition totals"
                disabled={loadingNutritionReview}
                onClick={() => void loadNutritionTotals()}
              >
                <RefreshCw
                  className={loadingNutritionReview ? 'animate-spin' : ''}
                />
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {hasNutritionTotals ? (
              <div className="grid grid-cols-3 gap-x-3 gap-y-4 rounded-2xl bg-orange-50 p-4 dark:bg-orange-950/25">
                {totals.map(([label, value, unit]) => (
                  <div key={label}>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="mt-1 font-semibold tabular-nums">
                      {Math.round(value)} {unit}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-2xl bg-muted/50 p-4 text-sm leading-6 text-muted-foreground">
                No analyzed meals have been logged yet. You can still complete
                the safety check without entering your meals again.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="mt-4 border-0 bg-card shadow-sm ring-border">
          <CardHeader>
            <CardTitle className="text-lg">What you ate</CardTitle>
            <CardDescription>
              Summarized from the meals you logged—not reconstructed from memory.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {nutritionMealSummaries.length ? (
              <ul className="space-y-2 text-sm leading-6">
                {nutritionMealSummaries.map((meal) => (
                  <li key={meal} className="rounded-xl bg-muted/50 px-3 py-2">
                    {meal}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">
                No meal descriptions are available for this day. The coach will
                use only the totals that were actually logged.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="mt-4 space-y-4">
          <Card className="border-0 bg-card shadow-sm ring-border">
            <CardHeader>
              <CardTitle className="text-lg">How was your hunger?</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {[
                ['comfortable', 'Comfortable'],
                ['hungrier', 'Hungrier than usual'],
                ['persistent', 'Persistently hungry'],
              ].map(([value, label]) => (
                <Button
                  key={value}
                  className="h-11 justify-start rounded-xl"
                  variant={
                    nutritionReviewDraft.hunger === value
                      ? 'default'
                      : 'secondary'
                  }
                  onClick={() =>
                    setNutritionReviewDraft((draft) => ({
                      ...draft,
                      hunger: value as NutritionReviewDraft['hunger'],
                    }))
                  }
                >
                  {nutritionReviewDraft.hunger === value && <Check />}
                  {label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card className="border-0 bg-card shadow-sm ring-border">
            <CardHeader>
              <CardTitle className="text-lg">How was your energy?</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {[
                ['steady', 'Steady'],
                ['low', 'Lower than usual'],
                ['weak_dizzy', 'Weak or dizzy'],
              ].map(([value, label]) => (
                <Button
                  key={value}
                  className="h-11 justify-start rounded-xl"
                  variant={
                    nutritionReviewDraft.energy === value
                      ? 'default'
                      : 'secondary'
                  }
                  onClick={() =>
                    setNutritionReviewDraft((draft) => ({
                      ...draft,
                      energy: value as NutritionReviewDraft['energy'],
                    }))
                  }
                >
                  {nutritionReviewDraft.energy === value && <Check />}
                  {label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card className="border-0 bg-card shadow-sm ring-border">
            <CardHeader>
              <CardTitle className="text-lg">
                Any breastfeeding concern?
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {[
                ['none', 'No concern'],
                ['reduced_supply', 'Possible reduced milk supply'],
                ['other', 'Another concern'],
              ].map(([value, label]) => (
                <Button
                  key={value}
                  className="h-11 justify-start rounded-xl"
                  variant={
                    nutritionReviewDraft.breastfeeding === value
                      ? 'default'
                      : 'secondary'
                  }
                  onClick={() =>
                    setNutritionReviewDraft((draft) => ({
                      ...draft,
                      breastfeeding:
                        value as NutritionReviewDraft['breastfeeding'],
                    }))
                  }
                >
                  {nutritionReviewDraft.breastfeeding === value && <Check />}
                  {label}
                </Button>
              ))}
            </CardContent>
          </Card>
        </div>

        {hasSafetyFlag && (
          <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
            Your Nutrition Coach will flag this in your review. If weakness,
            dizziness, persistent hunger, reduced milk supply, or another
            feeding concern continues, contact your clinician or lactation
            professional.
          </div>
        )}

        {reviewComplete && (
          <Card className="mt-4 border-0 bg-card shadow-sm ring-border">
            <CardHeader>
              <CardTitle className="text-lg">Reflect with your coach</CardTitle>
              <CardDescription>
                Discuss how the day felt and agree on small changes for tomorrow.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {activeNutritionMessages.length ? (
                <div className="mb-3 max-h-80 space-y-3 overflow-y-auto">
                  {activeNutritionMessages.map((message, index) => (
                    <div
                      key={`${message.role}-${index}`}
                      className={`rounded-2xl px-3.5 py-3 text-sm leading-6 ${message.role === 'user' ? 'ml-8 bg-primary text-primary-foreground' : 'mr-4 bg-muted/60'}`}
                    >
                      <p className="whitespace-pre-wrap">{message.text}</p>
                    </div>
                  ))}
                  {chatting && (
                    <div className="mr-4 inline-flex items-center gap-2 rounded-2xl bg-muted/60 px-3.5 py-3 text-sm">
                      <LoaderCircle className="size-4 animate-spin" /> Thinking…
                    </div>
                  )}
                </div>
              ) : (
                <Button
                  className="h-11 w-full rounded-xl"
                  disabled={chatting}
                  onClick={() => void sendNutritionReviewMessage(true)}
                >
                  {chatting ? (
                    <LoaderCircle className="animate-spin" />
                  ) : (
                    <Sparkles />
                  )}
                  Review my day
                </Button>
              )}

              {activeNutritionMessages.length > 0 && (
                <div className="flex items-end gap-2">
                  <Textarea
                    value={checkInResponse}
                    onChange={(event) => setCheckInResponse(event.target.value)}
                    placeholder="Reply to your Nutrition Coach…"
                    className="min-h-12 flex-1 resize-none rounded-2xl"
                    disabled={chatting}
                  />
                  <Button
                    size="icon"
                    className="size-11 shrink-0 rounded-full"
                    aria-label="Send nutrition reflection"
                    disabled={!checkInResponse.trim() || chatting}
                    onClick={() => void sendNutritionReviewMessage(false)}
                  >
                    {chatting ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <Send />
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button
            className="h-11 rounded-xl"
            disabled={!reviewComplete || !hasCoachReply || savingCheckIn}
            onClick={() => void saveNutritionReview()}
          >
            {savingCheckIn ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Check />
            )}
            Finish reflection
          </Button>
          <Button
            className="h-11 rounded-xl"
            variant="ghost"
            disabled={savingCheckIn}
            onClick={() => void submitCheckIn('skipped')}
          >
            {viewingToday ? 'Skip today' : 'Skip this day'}
          </Button>
        </div>
      </>
    );
  };

  const renderWellbeingRoutine = (checkIn: CheckIn) => {
    const morning = isWakeUpRoutine(checkIn);
    const totalSteps = morning ? 5 : 3;
    const timerMinutes = Math.floor(meditationSeconds / 60)
      .toString()
      .padStart(2, '0');
    const timerSeconds = (meditationSeconds % 60).toString().padStart(2, '0');
    const stepIsComplete = morning
      ? [
          Boolean(wellbeingDraft.accomplishments.trim()),
          Boolean(wellbeingDraft.gratitude.trim()),
          wellbeingDraft.morningAffirmations,
          wellbeingDraft.meditationComplete,
          Boolean(wellbeingDraft.oneAction.trim()),
        ][wellbeingStep]
      : [
          Boolean(wellbeingDraft.emotionalDump.trim()),
          wellbeingDraft.actionCompleted !== null,
          wellbeingDraft.eveningAffirmations,
        ][wellbeingStep];

    const affirmationsPanel = (
      <div className="space-y-3">
        <p className="text-sm leading-6 text-muted-foreground">
          Read these aloud slowly. You can repeat them once more later today.
        </p>
        <ol className="space-y-3">
          {AFFIRMATIONS.map((affirmation, index) => (
            <li
              key={affirmation}
              className="flex gap-3 rounded-2xl bg-rose-50 p-3.5 text-sm leading-6 ring-1 ring-rose-100 dark:bg-rose-950/25 dark:ring-rose-900"
            >
              <span className="font-semibold text-rose-700 dark:text-rose-300">
                {index + 1}.
              </span>
              <span>{affirmation}</span>
            </li>
          ))}
        </ol>
        <Button
          className="h-11 w-full rounded-xl"
          variant={
            (
              morning
                ? wellbeingDraft.morningAffirmations
                : wellbeingDraft.eveningAffirmations
            )
              ? 'secondary'
              : 'default'
          }
          onClick={() =>
            setWellbeingDraft((draft) =>
              morning
                ? { ...draft, morningAffirmations: true }
                : { ...draft, eveningAffirmations: true },
            )
          }
        >
          <Check /> I recited the affirmations
        </Button>
      </div>
    );

    const morningSteps = [
      {
        title: 'Accomplishments',
        description:
          'Write three things you accomplished and feel proud of from the last day. Add all three in one entry.',
        content: (
          <Textarea
            value={wellbeingDraft.accomplishments}
            onChange={(event) =>
              setWellbeingDraft((draft) => ({
                ...draft,
                accomplishments: event.target.value,
              }))
            }
            placeholder={'1. …\n2. …\n3. …'}
            className="min-h-44 bg-background text-base leading-6"
          />
        ),
      },
      {
        title: 'Gratitude',
        description:
          'Write three things you are grateful for. You can also note the people you texted and why you appreciate them.',
        content: (
          <Textarea
            value={wellbeingDraft.gratitude}
            onChange={(event) =>
              setWellbeingDraft((draft) => ({
                ...draft,
                gratitude: event.target.value,
              }))
            }
            placeholder={'1. …\n2. …\n3. …'}
            className="min-h-44 bg-background text-base leading-6"
          />
        ),
      },
      {
        title: 'Affirmations',
        description: 'Recite each affirmation aloud.',
        content: affirmationsPanel,
      },
      {
        title: 'Meditation',
        description:
          'Meditate for ten minutes here, or complete a session in Insight Timer.',
        content: (
          <div className="text-center">
            <p className="font-heading text-6xl font-semibold tabular-nums tracking-tight">
              {timerMinutes}:{timerSeconds}
            </p>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <Button
                className="h-11 rounded-xl"
                onClick={() => setMeditationRunning((running) => !running)}
                disabled={meditationSeconds === 0}
              >
                {meditationRunning ? 'Pause' : 'Start timer'}
              </Button>
              <Button
                className="h-11 rounded-xl"
                variant="secondary"
                onClick={() => {
                  setMeditationRunning(false);
                  setMeditationSeconds(10 * 60);
                  setWellbeingDraft((draft) => ({
                    ...draft,
                    meditationComplete: false,
                  }));
                }}
              >
                Reset
              </Button>
            </div>
            <a
              href="https://insighttimer.com/meditation-timer"
              onClick={persistResumeState}
              className="mt-4 block text-sm font-semibold text-primary underline underline-offset-4"
            >
              Open Insight Timer app
            </a>
            <Button
              className="mt-3 h-10 w-full rounded-xl"
              variant="ghost"
              onClick={() => {
                setMeditationRunning(false);
                setWellbeingDraft((draft) => ({
                  ...draft,
                  meditationComplete: true,
                }));
              }}
            >
              <Check /> I completed ten minutes elsewhere
            </Button>
          </div>
        ),
      },
      {
        title: 'One Action',
        description:
          'Write one concrete action you will take today to move in the direction you want to go. The Wind-down Routine will bring it back tonight.',
        content: (
          <Textarea
            value={wellbeingDraft.oneAction}
            onChange={(event) =>
              setWellbeingDraft((draft) => ({
                ...draft,
                oneAction: event.target.value,
              }))
            }
            placeholder="Today I will…"
            className="min-h-36 bg-background text-base leading-6"
          />
        ),
      },
    ];

    const eveningSteps = [
      {
        title: 'Emotional Dump',
        description:
          'Write freely about what is on your mind. This entry remains in your private Life OS database.',
        content: (
          <Textarea
            value={wellbeingDraft.emotionalDump}
            onChange={(event) =>
              setWellbeingDraft((draft) => ({
                ...draft,
                emotionalDump: event.target.value,
              }))
            }
            placeholder="What is on your mind right now?"
            className="min-h-52 bg-background text-base leading-6"
          />
        ),
      },
      {
        title: 'Today’s One Action',
        description: morningAction
          ? `This morning you planned: “${morningAction}” Did you complete it?`
          : 'Did you complete the one action you chose for today?',
        content: (
          <div className="grid grid-cols-2 gap-2">
            <Button
              className="h-12 rounded-xl"
              variant={
                wellbeingDraft.actionCompleted === true
                  ? 'default'
                  : 'secondary'
              }
              onClick={() =>
                setWellbeingDraft((draft) => ({
                  ...draft,
                  actionCompleted: true,
                }))
              }
            >
              Yes, I did
            </Button>
            <Button
              className="h-12 rounded-xl"
              variant={
                wellbeingDraft.actionCompleted === false
                  ? 'default'
                  : 'secondary'
              }
              onClick={() =>
                setWellbeingDraft((draft) => ({
                  ...draft,
                  actionCompleted: false,
                }))
              }
            >
              Not today
            </Button>
          </div>
        ),
      },
      {
        title: 'Evening Affirmations',
        description: 'Read your affirmations once more before winding down.',
        content: affirmationsPanel,
      },
    ];
    const step = (morning ? morningSteps : eveningSteps)[wellbeingStep];

    return (
      <>
        <PageHeader
          title={morning ? 'Wake-up Routine' : 'Wind-down Routine'}
          subtitle="Inner Wellbeing Guru"
        />
        <div className="mt-3 flex items-center justify-between text-xs font-semibold text-muted-foreground">
          <span>
            Step {wellbeingStep + 1} of {totalSteps}
          </span>
          <span>{Math.round(((wellbeingStep + 1) / totalSteps) * 100)}%</span>
        </div>
        <Progress
          value={((wellbeingStep + 1) / totalSteps) * 100}
          className="mt-2"
        />
        <Card className="mt-5 border-0 bg-card shadow-sm ring-border">
          <CardHeader>
            <CardTitle className="text-2xl">{step.title}</CardTitle>
            <CardDescription className="text-sm leading-6">
              {step.description}
            </CardDescription>
          </CardHeader>
          <CardContent>{step.content}</CardContent>
        </Card>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button
            className="h-11 rounded-xl"
            variant="secondary"
            disabled={wellbeingStep === 0 || savingWellbeing}
            onClick={() => setWellbeingStep((current) => current - 1)}
          >
            Back
          </Button>
          <Button
            className="h-11 rounded-xl"
            disabled={!stepIsComplete || savingWellbeing}
            onClick={() => {
              if (wellbeingStep < totalSteps - 1) {
                setWellbeingStep((current) => current + 1);
              } else {
                void saveWellbeingRoutine();
              }
            }}
          >
            {savingWellbeing ? (
              <LoaderCircle className="animate-spin" />
            ) : wellbeingStep === totalSteps - 1 ? (
              'Complete routine'
            ) : (
              'Next'
            )}
          </Button>
        </div>
        <Button
          className="mt-2 h-10 w-full rounded-xl"
          variant="ghost"
          disabled={savingWellbeing}
          onClick={() => void submitCheckIn('skipped')}
        >
          Skip routine
        </Button>
      </>
    );
  };

  const renderCheckIn = () =>
    activeCheckIn && isNutritionReview(activeCheckIn) ? (
      renderNutritionReview(activeCheckIn)
    ) : activeCheckIn?.agent_id === 'nutrition_coach' &&
      usesInputLogging(activeCheckIn) ? (
      renderNutritionCheckIn(activeCheckIn)
    ) : isWakeUpRoutine(activeCheckIn) || isWindDownRoutine(activeCheckIn) ? (
      renderWellbeingRoutine(activeCheckIn)
    ) : (
      <>
        <PageHeader
          title="Daily check-in"
          subtitle={`${userCheckIns.length} remaining`}
        />
        {activeCheckIn ? (
          <div className="mt-5">
            <div className="mb-4 flex items-center gap-3">
              <AgentMark agentId={activeCheckIn.agent_id} />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Now with
                </p>
                <h2 className="font-heading text-lg font-semibold">
                  {formatAgent(activeCheckIn.agent_id)}
                </h2>
              </div>
            </div>
            <Card className="border-0 bg-card shadow-sm ring-border">
              <CardHeader>
                {activeCheckIn.agent_id === 'nutrition_coach' &&
                usesInputLogging(activeCheckIn) ? (
                  <>
                    <CardDescription>Planned meal</CardDescription>
                    <CardTitle className="text-xl leading-7">
                      {shortTaskTitle(activeCheckIn)}
                    </CardTitle>
                    <p className="text-sm leading-6 text-muted-foreground">
                      {compactTaskScope(
                        activeCheckIn,
                        goals.find((goal) => goal.id === activeCheckIn.goal_id),
                      )}
                    </p>
                  </>
                ) : (
                  <>
                    <CardTitle className="text-xl leading-7">
                      {friendlyPrompt(activeCheckIn.prompt)}
                    </CardTitle>
                    <CardDescription>
                      Answer honestly. Partial progress still counts as useful
                      information.
                    </CardDescription>
                  </>
                )}
              </CardHeader>
              <CardContent>
                {activeCheckIn.agent_id === 'nutrition_coach' &&
                usesInputLogging(activeCheckIn) ? (
                  <>
                    <div className="overflow-hidden rounded-2xl border border-border bg-background/65">
                      <div className="max-h-[26rem] space-y-3 overflow-y-auto p-3">
                        {activeNutritionMessages.length === 0 &&
                          !activeNutritionAnalysis && (
                            <div className="rounded-2xl rounded-bl-md bg-orange-50 px-4 py-3 text-sm leading-5 ring-1 ring-orange-200 dark:bg-orange-950/30 dark:ring-orange-800">
                              Tell me what you ate, or tap the camera to take a
                              photo or choose one from your library. I’ll
                              estimate calories, macros, fibre, and calcium.
                            </div>
                          )}
                        {activeNutritionMessages.length === 0 &&
                          activeNutritionAnalysis && (
                            <NutritionEstimateCard
                              analysis={activeNutritionAnalysis}
                            />
                          )}
                        {activeNutritionMessages.map((message, index) => (
                          <div
                            key={`${message.role}-${index}`}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            {message.analysis ? (
                              <div className="w-full max-w-[94%]">
                                <NutritionEstimateCard
                                  analysis={message.analysis}
                                />
                              </div>
                            ) : (
                              <div
                                className={`max-w-[86%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-5 ${message.role === 'user' ? 'rounded-br-md bg-primary text-primary-foreground' : 'rounded-bl-md bg-orange-50 ring-1 ring-orange-200 dark:bg-orange-950/30 dark:ring-orange-800'}`}
                              >
                                {message.text}
                              </div>
                            )}
                          </div>
                        ))}
                        {(uploadingPhoto || analyzingNutrition) && (
                          <div className="flex justify-start">
                            <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md bg-orange-50 px-4 py-3 text-sm ring-1 ring-orange-200 dark:bg-orange-950/30 dark:ring-orange-800">
                              <LoaderCircle className="size-4 animate-spin" />
                              Nutrition Coach is estimating…
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="flex items-end gap-2 border-t border-border bg-card p-2">
                        <label
                          className={`flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-secondary text-secondary-foreground active:scale-[.98] ${uploadingPhoto ? 'pointer-events-none opacity-50' : ''}`}
                          aria-label="Take or choose a meal photo"
                        >
                          <Camera className="size-5" />
                          <input
                            className="sr-only"
                            type="file"
                            accept="image/*"
                            disabled={uploadingPhoto || analyzingNutrition}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) {
                                if (file.size > 12 * 1024 * 1024) {
                                  setError(
                                    'Choose a photo smaller than 12 MB.',
                                  );
                                } else {
                                  void uploadPhoto(file);
                                }
                              }
                              event.currentTarget.value = '';
                            }}
                          />
                        </label>
                        <Textarea
                          value={checkInResponse}
                          onChange={(event) =>
                            setCheckInResponse(event.target.value)
                          }
                          onKeyDown={(event) => {
                            if (
                              event.key === 'Enter' &&
                              !event.shiftKey &&
                              checkInResponse.trim()
                            ) {
                              event.preventDefault();
                              void sendNutritionMessage();
                            }
                          }}
                          placeholder="Describe what you ate or correct the estimate…"
                          className="max-h-28 min-h-11 resize-none rounded-2xl bg-background py-3"
                        />
                        <Button
                          size="icon"
                          className="size-11 shrink-0 rounded-full"
                          aria-label="Send message"
                          disabled={
                            !checkInResponse.trim() ||
                            analyzingNutrition ||
                            uploadingPhoto
                          }
                          onClick={() => void sendNutritionMessage()}
                        >
                          {analyzingNutrition ? (
                            <LoaderCircle className="animate-spin" />
                          ) : (
                            <Send />
                          )}
                        </Button>
                      </div>
                    </div>

                    <Button
                      className="mt-4 h-11 w-full rounded-xl"
                      disabled={!activeNutritionAnalysis || savingCheckIn}
                      onClick={() => void submitCheckIn('done')}
                    >
                      {savingCheckIn ? (
                        <LoaderCircle className="animate-spin" />
                      ) : (
                        <Check />
                      )}
                      Log this
                    </Button>
                    <Button
                      className="mt-2 h-10 w-full rounded-xl"
                      variant="ghost"
                      disabled={savingCheckIn}
                      onClick={() => void submitCheckIn('skipped')}
                    >
                      {viewingToday ? 'Skip for today' : 'Skip this day'}
                    </Button>
                  </>
                ) : (
                  <>
                    {usesInputLogging(activeCheckIn) && (
                      <>
                        {activeCheckIn.agent_id === 'nutrition_coach' && (
                          <div className="mb-3">
                            <p className="font-semibold">What did you eat?</p>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                              Describe the food and approximate portions, or add
                              a photo below.
                            </p>
                          </div>
                        )}
                        <Textarea
                          value={checkInResponse}
                          onChange={(event) =>
                            setCheckInResponse(event.target.value)
                          }
                          placeholder={
                            activeCheckIn.agent_id === 'nutrition_coach'
                              ? 'Example: Two eggs, one small roti, vegetables, and about 25 g cheese…'
                              : 'Add a short note, measurement, or reflection…'
                          }
                          className="min-h-28 bg-background"
                        />
                        {activeCheckIn.agent_id === 'nutrition_coach' && (
                          <Button
                            className="mt-3 h-11 w-full rounded-xl"
                            variant="secondary"
                            disabled={
                              !checkInResponse.trim() || analyzingNutrition
                            }
                            onClick={() => void sendNutritionMessage()}
                          >
                            {analyzingNutrition ? (
                              <LoaderCircle className="animate-spin" />
                            ) : (
                              <Sparkles />
                            )}
                            Analyze Description
                          </Button>
                        )}
                        {supportsPhoto(activeCheckIn) && (
                          <div className="mt-4 rounded-2xl border border-border bg-background/65 p-3">
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-sm font-semibold">
                                  {activeCheckIn.agent_id === 'nutrition_coach'
                                    ? 'Or add a meal photo'
                                    : supportsPrivateAttachment(activeCheckIn)
                                      ? 'Attach your work'
                                      : 'Photo evidence'}
                                </p>
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                  {activeCheckIn.agent_id === 'nutrition_coach'
                                    ? 'The Nutrition Coach will estimate the meal automatically'
                                    : supportsPrivateAttachment(activeCheckIn)
                                      ? 'Add a photo or screenshot · stored privately'
                                      : 'Camera or recent photos · stored privately'}
                                </p>
                              </div>
                              <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-xl bg-secondary px-3 text-sm font-semibold text-secondary-foreground active:scale-[.98]">
                                <Camera className="size-4" /> Add photo
                                <input
                                  className="sr-only"
                                  type="file"
                                  accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                                  onChange={(event) =>
                                    choosePhoto(event.target.files?.[0])
                                  }
                                />
                              </label>
                            </div>

                            {photoPreview && photoFile && (
                              <div className="mt-3 overflow-hidden rounded-xl border border-border bg-card">
                                <Image
                                  src={photoPreview}
                                  alt="Selected evidence preview"
                                  width={640}
                                  height={480}
                                  unoptimized
                                  className="max-h-64 w-full object-cover"
                                />
                                <div className="p-3">
                                  {activeCheckIn.agent_id !==
                                    'nutrition_coach' &&
                                    !supportsPrivateAttachment(activeCheckIn) && (
                                    <label className="flex cursor-pointer items-start gap-2 text-xs leading-5 text-muted-foreground">
                                      <input
                                        type="checkbox"
                                        className="mt-1 size-4 accent-primary"
                                        checked={analyzePhoto}
                                        onChange={(event) =>
                                          setAnalyzePhoto(event.target.checked)
                                        }
                                      />
                                      <span>
                                        Analyze with this coach. This sends this
                                        photo to the configured model and stores
                                        its observations.
                                      </span>
                                    </label>
                                  )}
                                  <Button
                                    className={`${activeCheckIn.agent_id === 'nutrition_coach' ? '' : 'mt-3'} h-10 w-full rounded-xl`}
                                    disabled={uploadingPhoto}
                                    onClick={() => void uploadPhoto()}
                                  >
                                    {uploadingPhoto ? (
                                      <LoaderCircle className="animate-spin" />
                                    ) : (
                                      <Camera />
                                    )}
                                    {activeCheckIn.agent_id ===
                                    'nutrition_coach'
                                      ? 'Analyze Photo'
                                      : supportsPrivateAttachment(activeCheckIn)
                                        ? 'Attach privately'
                                      : analyzePhoto
                                        ? 'Save and analyze'
                                        : 'Save privately'}
                                  </Button>
                                </div>
                              </div>
                            )}

                            {activePhotos.length > 0 && (
                              <div className="mt-3 space-y-2">
                                <p className="text-xs font-semibold text-primary">
                                  {activePhotos.length} photo
                                  {activePhotos.length === 1 ? '' : 's'} stored
                                </p>
                                {activePhotos.map((photo) => (
                                  <div
                                    key={photo.id}
                                    className="rounded-xl bg-card px-3 py-2 text-xs leading-5 ring-1 ring-border"
                                  >
                                    {photo.analysis &&
                                    activeCheckIn.agent_id ===
                                      'nutrition_coach' ? (
                                      <p className="font-semibold text-primary">
                                        Meal photo saved and analyzed.
                                      </p>
                                    ) : photo.analysis ? (
                                      <>
                                        <p className="font-semibold">
                                          Coach’s photo analysis
                                        </p>
                                        <p className="mt-1 text-muted-foreground">
                                          {photo.analysis.summary}
                                        </p>
                                        {photo.analysis.estimated_calories !==
                                          null && (
                                          <p className="mt-1 font-semibold text-primary">
                                            Rough estimate:{' '}
                                            {Math.round(
                                              photo.analysis.estimated_calories,
                                            )}{' '}
                                            calories
                                          </p>
                                        )}
                                      </>
                                    ) : (
                                      <p className="text-muted-foreground">
                                        {photo.analysis_status === 'unavailable'
                                          ? 'Photo saved. Analysis was unavailable, so no estimate was recorded.'
                                          : 'Photo saved locally without model analysis.'}
                                      </p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        {activeCheckIn.agent_id === 'nutrition_coach' &&
                          activeNutritionAnalysis && (
                            <NutritionEstimateCard
                              analysis={activeNutritionAnalysis}
                            />
                          )}
                      </>
                    )}
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      <Button
                        className="h-11 rounded-xl"
                        disabled={savingCheckIn}
                        onClick={() => void submitCheckIn('done')}
                      >
                        <Check />
                        {usesInputLogging(activeCheckIn) ? 'Log this' : 'Done'}
                      </Button>
                      <Button
                        className="h-11 rounded-xl"
                        variant="ghost"
                        disabled={savingCheckIn}
                        onClick={() => void submitCheckIn('skipped')}
                      >
                        Skip
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
            <p className="mt-4 text-center text-xs text-muted-foreground">
              Saved privately to your local Life OS database.
            </p>
          </div>
        ) : (
          <Card className="mt-6 border-0 bg-card ring-border">
            <CardContent className="py-10 text-center">
              <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-success text-white">
                <Check />
              </span>
              <h2 className="mt-4 font-heading text-xl font-semibold">
                Check-in complete
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {agentDeliveries.length
                  ? agentDeliveries.length === 1
                    ? 'One automatic agent delivery is still scheduled. You do not need to enter anything for it.'
                    : `${agentDeliveries.length} automatic agent deliveries are still scheduled. You do not need to enter anything for them.`
                  : 'Every due prompt has a response.'}
              </p>
              <Button
                className="mt-5 rounded-full"
                onClick={() => setView('today')}
              >
                Return to selected day
              </Button>
            </CardContent>
          </Card>
        )}
      </>
    );

  const renderAgents = () => {
    if (selectedAgent) {
      const history = messages[selectedAgent.id] || [];
      return (
        <>
          <header className="flex items-center gap-3 py-4">
            <Button
              aria-label="Back to agents"
              variant="ghost"
              size="icon-lg"
              className="rounded-full"
              onClick={() => setSelectedAgent(null)}
            >
              <ArrowLeft />
            </Button>
            <AgentMark agentId={selectedAgent.id} />
            <div className="min-w-0">
              <h1 className="truncate font-heading text-xl font-semibold">
                {selectedAgent.name}
              </h1>
              <p className="truncate text-xs text-muted-foreground">
                {selectedAgent.purpose}
              </p>
            </div>
          </header>
          <div className="mt-3 min-h-[48vh] space-y-3">
            {!history.length && (
              <Card className="border-0 bg-card ring-border">
                <CardContent>
                  <p className="font-semibold">
                    What would you like help with?
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    This conversation uses only this agent’s approved goals and
                    minimum relevant context.
                  </p>
                </CardContent>
              </Card>
            )}
            {history.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'rounded-br-md bg-primary text-primary-foreground' : 'rounded-bl-md bg-card ring-1 ring-border'}`}
                >
                  {message.text}
                </div>
              </div>
            ))}
            {chatting && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoaderCircle className="size-4 animate-spin" />{' '}
                {selectedAgent.name} is thinking…
              </div>
            )}
          </div>
          <div className="sticky bottom-20 mt-5 rounded-2xl border border-border bg-background/95 p-2 shadow-lg backdrop-blur">
            <Textarea
              value={chatDraft}
              onChange={(event) => setChatDraft(event.target.value)}
              placeholder={`Message ${selectedAgent.name}…`}
              className="min-h-20 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
            />
            <div className="flex justify-end">
              <Button
                size="icon-lg"
                className="rounded-full"
                disabled={!chatDraft.trim() || chatting}
                onClick={() => void sendChat()}
                aria-label="Send message"
              >
                <Send />
              </Button>
            </div>
          </div>
        </>
      );
    }
    return (
      <>
        <PageHeader title="Your company" subtitle="Choose an agent to begin" />
        <Card className="mt-5 border-0 bg-gradient-to-br from-zinc-950 to-zinc-800 text-white ring-white/10">
          <CardContent className="py-5">
            <div className="flex items-start gap-3">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-lime-300 text-zinc-950">
                <Watch className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-heading text-lg font-semibold">WHOOP</p>
                  {whoopStatus.connected && (
                    <span className="rounded-full bg-lime-300/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-lime-200">
                      Connected
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm leading-5 text-zinc-300">
                  Recovery, sleep, day strain, and workouts for your Fitness
                  Coach.
                </p>
              </div>
            </div>
            <Button
              className="mt-4 w-full rounded-xl bg-lime-300 text-zinc-950 hover:bg-lime-200"
              disabled={whoopBusy || !whoopStatus.configured}
              onClick={() =>
                void (whoopStatus.connected ? syncWhoop() : connectWhoop())
              }
            >
              {whoopBusy ? (
                <LoaderCircle className="animate-spin" />
              ) : whoopStatus.connected ? (
                <RefreshCw />
              ) : (
                <Watch />
              )}
              {!whoopStatus.configured
                ? 'Finish WHOOP setup'
                : whoopStatus.connected
                  ? 'Sync WHOOP now'
                  : 'Connect WHOOP'}
            </Button>
            {whoopMessage && (
              <p className="mt-3 text-xs leading-5 text-zinc-300">
                {whoopMessage}
              </p>
            )}
          </CardContent>
        </Card>
        <Card className="mt-5 border-0 bg-card ring-border">
          <CardContent className="py-4">
            <div>
              <p className="font-semibold">Appearance</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Choose how Life OS looks on this device.
              </p>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-1 rounded-2xl bg-muted/70 p-1">
              {(
                [
                  { value: 'system', label: 'System', icon: Monitor },
                  { value: 'light', label: 'Light', icon: Sun },
                  { value: 'dark', label: 'Dark', icon: Moon },
                ] as const
              ).map(({ value, label, icon: Icon }) => {
                const active = themePreference === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={active}
                    onClick={() => chooseTheme(value)}
                    className={`flex min-h-11 items-center justify-center gap-1.5 rounded-xl px-2 text-xs font-semibold transition-colors ${
                      active
                        ? 'bg-card text-foreground shadow-sm'
                        : 'text-muted-foreground'
                    }`}
                  >
                    <Icon className="size-4" />
                    {label}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
        <div className="mt-5 space-y-3">
          {agents.map((agent) => (
            <button
              key={agent.id}
              aria-label={`Talk to ${agent.name}`}
              onClick={() => setSelectedAgent(agent)}
              className="block w-full text-left"
            >
              <Card
                size="sm"
                className="border-0 bg-card ring-border transition-transform active:scale-[.99]"
              >
                <CardContent className="flex items-center gap-3">
                  <AgentMark agentId={agent.id} />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{agent.name}</p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">
                      {agent.purpose}
                    </p>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      </>
    );
  };

  const renderBriefing = () => (
    <>
      <header className="flex items-center gap-3 py-4">
        <Button
          size="icon-lg"
          variant="ghost"
          className="shrink-0 rounded-full"
          aria-label="Back to selected day"
          onClick={() => setView('today')}
        >
          <ArrowLeft />
        </Button>
        <AgentMark agentId="briefing_intern" />
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Briefing Officer
          </p>
          <h1 className="truncate font-heading text-2xl font-semibold">
            Daily Briefing
          </h1>
        </div>
      </header>

      {loadingBriefing && <LoadingCard />}

      {!loadingBriefing && briefingError && (
        <Card className="mt-3 border-0 bg-card ring-border">
          <CardContent className="py-8 text-center">
            <Newspaper className="mx-auto size-8 text-violet-700" />
            <h2 className="mt-3 font-heading text-xl font-semibold">
              Briefing not ready
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {briefingError}
            </p>
            <Button
              className="mt-4 rounded-full"
              variant="secondary"
              onClick={() => setBriefingAttempt((attempt) => attempt + 1)}
            >
              <RefreshCw /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {!loadingBriefing && briefing && (
        <>
          <div className="mt-3 rounded-3xl bg-violet-50 p-5 ring-1 ring-violet-100 dark:bg-violet-950/25 dark:ring-violet-900">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-violet-700 dark:text-violet-300">
              Private briefing · {displayDate}
            </p>
            <h2 className="mt-2 font-heading text-3xl font-semibold leading-9 tracking-tight">
              {briefing.title}
            </h2>
          </div>
          <div className="mt-5 rounded-3xl bg-card px-5 py-6 shadow-sm ring-1 ring-border">
            <BriefingBody markdown={briefing.markdown} />
          </div>
          <Button
            className={`mt-5 w-full rounded-full ${
              briefingReviewed
                ? 'bg-emerald-100 text-emerald-900 hover:bg-emerald-100'
                : ''
            }`}
            variant={briefingReviewed ? 'secondary' : 'default'}
            disabled={briefingReviewed}
            onClick={() => void markBriefingReviewed()}
          >
            <Check />
            {briefingReviewed ? 'Briefing reviewed' : 'Mark as reviewed'}
          </Button>
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Saved privately as {briefing.source_file}
          </p>
        </>
      )}
    </>
  );

  const renderAppointmentSync = () => {
    const processedAt = appointmentSync
      ? new Intl.DateTimeFormat(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        }).format(new Date(appointmentSync.processed_at))
      : '';
    const hasExceptions = appointmentSync?.items.some((item) => item.exception);
    const statistics = appointmentSync
      ? [
          ['Created', appointmentSync.events_created],
          ['Updated', appointmentSync.events_updated],
          ['Cancelled', appointmentSync.events_cancelled],
          ['Already existed', appointmentSync.existing_events_matched],
        ]
      : [];

    return (
      <>
        <header className="flex items-center gap-3 py-4">
          <Button
            size="icon-lg"
            variant="ghost"
            className="shrink-0 rounded-full"
            aria-label="Back to selected day"
            onClick={() => setView('today')}
          >
            <ArrowLeft />
          </Button>
          <AgentMark agentId="operations_manager" />
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Operations Manager
            </p>
            <h1 className="font-heading text-2xl font-semibold">
              Appointment &amp; Calendar Sync
            </h1>
          </div>
        </header>

        {loadingAppointmentSync && <LoadingCard />}

        {!loadingAppointmentSync && appointmentSyncError && (
          <Card className="mt-3 border-0 bg-card ring-border">
            <CardContent className="py-8 text-center">
              <CalendarDays className="mx-auto size-8 text-emerald-700" />
              <h2 className="mt-3 font-heading text-xl font-semibold">
                Sync report not ready
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {appointmentSyncError}
              </p>
              <Button
                className="mt-4 rounded-full"
                variant="secondary"
                onClick={() =>
                  setAppointmentSyncAttempt((attempt) => attempt + 1)
                }
              >
                <RefreshCw /> Try again
              </Button>
            </CardContent>
          </Card>
        )}

        {!loadingAppointmentSync && appointmentSync && (
          <>
            <div
              className={`mt-3 rounded-3xl p-5 ring-1 ${
                hasExceptions
                  ? 'bg-amber-50 text-amber-950 ring-amber-200 dark:bg-amber-950/25 dark:text-amber-100 dark:ring-amber-900'
                  : 'bg-emerald-50 text-emerald-950 ring-emerald-200 dark:bg-emerald-950/25 dark:text-emerald-100 dark:ring-emerald-900'
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
                    hasExceptions
                      ? 'bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100'
                      : 'bg-emerald-600 text-white'
                  }`}
                >
                  {hasExceptions ? <TriangleAlert /> : <Check />}
                </span>
                <div>
                  <p className="font-heading text-xl font-semibold">
                    {hasExceptions
                      ? 'Completed with an exception'
                      : 'Sync completed'}
                  </p>
                  <p className="mt-1 text-sm opacity-75">{processedAt}</p>
                  <p className="mt-2 text-sm leading-6">
                    {appointmentSync.emails_processed}{' '}
                    {appointmentSync.emails_processed === 1 ? 'email' : 'emails'}{' '}
                    reviewed for confirmed appointment changes.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              {statistics.map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border"
                >
                  <p className="text-2xl font-bold tabular-nums">{value}</p>
                  <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {label}
                  </p>
                </div>
              ))}
            </div>

            <section className="mt-7">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Run details
              </p>
              <div className="mt-3 space-y-3">
                {appointmentSync.items.length ? (
                  appointmentSync.items.map((item, index) => (
                    <Card
                      key={`${item.action}-${index}`}
                      className={`border-0 ring-1 ${
                        item.exception
                          ? 'bg-amber-50 ring-amber-200 dark:bg-amber-950/20 dark:ring-amber-900'
                          : 'bg-card ring-border'
                      }`}
                    >
                      <CardContent className="flex items-start gap-3">
                        <span
                          className={`mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full ${
                            item.exception
                              ? 'bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100'
                              : 'bg-emerald-100 text-emerald-800'
                          }`}
                        >
                          {item.exception ? (
                            <TriangleAlert className="size-5" />
                          ) : (
                            <Check className="size-5" />
                          )}
                        </span>
                        <div className="min-w-0">
                          <h2 className="font-semibold">{item.action}</h2>
                          {item.event_date && (
                            <p className="mt-1 text-xs font-medium text-muted-foreground">
                              {new Intl.DateTimeFormat(undefined, {
                                dateStyle: 'medium',
                              }).format(localDateFromKey(item.event_date))}
                              {item.event_time ? ` · ${item.event_time}` : ''}
                            </p>
                          )}
                          <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            {item.summary}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                ) : (
                  <Card className="border-0 bg-card ring-border">
                    <CardContent className="flex items-center gap-3">
                      <span className="flex size-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-800">
                        <Check className="size-5" />
                      </span>
                      <p className="text-sm leading-6">
                        No confirmed appointment changes required a calendar update.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </section>

            <p className="mt-5 text-center text-xs leading-5 text-muted-foreground">
              This report stores only the minimum appointment outcome. Email bodies
              and unrelated private details are not displayed.
            </p>
          </>
        )}
      </>
    );
  };

  const renderFinance = () => (
    <>
      <PageHeader title="Daily Expense Summary" subtitle="Chief Finance Officer" />
      <div className="mt-5 flex items-center gap-3">
        <AgentMark agentId="chief_finance_officer" />
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Inbox expense capture
          </p>
          <p className="font-heading text-lg font-semibold">{displayDate}</p>
        </div>
      </div>

      <Card className="mt-5 overflow-hidden border-0 bg-gradient-to-br from-emerald-700 to-teal-900 text-white shadow-lg ring-0">
        <CardContent>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-white/70">
            Confirmed spending
          </p>
          {financeReport?.summaries.length ? (
            <div className="mt-3 space-y-4">
              {financeReport.summaries.map((summary) => (
                <div key={summary.currency}>
                  <p className="text-4xl font-bold tabular-nums">
                    {formatMoney(summary.net_spent, summary.currency)}
                  </p>
                  <p className="mt-1 text-sm text-white/75">
                    {formatMoney(summary.total_spent, summary.currency)} spent
                    {summary.total_refunded > 0
                      ? ` · ${formatMoney(summary.total_refunded, summary.currency)} refunded`
                      : ''}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3">
              <p className="text-3xl font-bold">No purchases found</p>
              <p className="mt-2 text-sm leading-6 text-white/75">
                The report will update after the Finance Officer processes this day’s email window.
              </p>
            </div>
          )}
          <div className="mt-5 grid grid-cols-2 gap-2">
            <div className="rounded-2xl bg-white/10 px-3 py-3">
              <p className="text-2xl font-bold tabular-nums">
                {financeReport?.purchase_count ?? 0}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/70">
                Purchases
              </p>
            </div>
            <div className="rounded-2xl bg-white/10 px-3 py-3">
              <p className="text-2xl font-bold tabular-nums">
                {financeReport?.processed_email_count ?? 0}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/70">
                Emails reviewed
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="mt-7">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Household inboxes
        </p>
        <Card className="mt-3 border-0 bg-card ring-border">
          <CardContent className="space-y-3 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold">Finance connections</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Read-only access; passwords are never stored.
                </p>
              </div>
              <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
                {financeAccounts.length} connected
              </span>
            </div>
            {financeAccounts.length > 0 ? (
              <div className="space-y-2">
                {financeAccounts.map((account) => (
                  <div
                    key={account.account_id}
                    className="flex items-center gap-3 rounded-2xl bg-muted/60 px-3 py-3"
                  >
                    <span className="flex size-9 items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
                      {account.member_name.slice(0, 1).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold">{account.member_name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {account.email}
                      </p>
                    </div>
                    <Check className="size-5 text-emerald-600" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-2xl bg-muted/60 px-3 py-3 text-sm text-muted-foreground">
                No local household inbox has been connected yet.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {financeReport?.summaries.map((summary) => (
        <section key={summary.currency} className="mt-7">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Category breakdown · {summary.currency}
          </p>
          <div className="mt-3 space-y-2">
            {summary.categories.map((category) => (
              <Card key={category.category} size="sm" className="border-0 bg-card ring-border">
                <CardContent className="flex items-center justify-between gap-4">
                  <p className="font-semibold">{formatCategory(category.category)}</p>
                  <p className="font-bold tabular-nums">
                    {formatMoney(category.amount, summary.currency)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}

      {financeReport && financeReport.transactions.length > 0 && (
        <section className="mt-7">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Transactions
          </p>
          <div className="mt-3 space-y-2">
            {financeReport.transactions.map((transaction) => (
              <Card key={transaction.id} size="sm" className="border-0 bg-card ring-border">
                <CardContent className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold">{transaction.merchant}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {transaction.household_member || 'Puja'} · {formatCategory(transaction.category)} · {transaction.kind === 'refund' ? 'Refund' : 'Purchase'}
                    </p>
                  </div>
                  <p className={`font-bold tabular-nums ${transaction.kind === 'refund' ? 'text-emerald-700' : ''}`}>
                    {transaction.kind === 'refund' ? '−' : ''}
                    {formatMoney(transaction.amount, transaction.currency)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      <p className="mt-6 text-center text-xs leading-5 text-muted-foreground">
        Stored privately. Currencies stay separate, and ambiguous emails are not counted as purchases.
      </p>
    </>
  );

  const renderProgress = () => {
    const eventTotal = (metric: string) =>
      dailyEvents
        .filter((event) => event.metric === metric)
        .reduce((total, event) => total + event.value, 0);
    const agentCheckIns = (agentId: string) =>
      checkIns.filter((checkIn) => checkIn.agent_id === agentId);
    const completedForAgent = (agentId: string) =>
      agentCheckIns(agentId).filter(
        (checkIn) =>
          checkIn.status === 'responded' && checkIn.outcome !== 'partial',
      ).length;
    const taskWasDone = (agentId: string, phrase: string) =>
      agentCheckIns(agentId).some(
        (checkIn) =>
          checkIn.prompt.toLowerCase().includes(phrase.toLowerCase()) &&
          checkIn.status === 'responded' &&
          checkIn.outcome !== 'partial',
      );
    const nutritionGoal = goals.find(
      (goal) => goal.owner_agent === 'nutrition_coach',
    );
    const nutritionTarget = (key: string) => {
      const metric = nutritionGoal?.metrics.find((item) => item.key === key);
      if (!metric) return null;
      if (metric.target_value !== null) return metric.target_value;
      if (metric.minimum_value !== null && metric.maximum_value !== null) {
        return (metric.minimum_value + metric.maximum_value) / 2;
      }
      return metric.minimum_value ?? metric.maximum_value;
    };
    const calorieBand = nutritionGoal?.success_definition.match(
      /([\d,]+)\s*[–—-]\s*([\d,]+)[-\s]*calorie/i,
    );
    const calorieMinimum = calorieBand
      ? Number(calorieBand[1].replaceAll(',', ''))
      : null;
    const calorieMaximum = calorieBand
      ? Number(calorieBand[2].replaceAll(',', ''))
      : null;
    const approvedCalorieTarget = nutritionTarget('daily_calories');
    const calorieTarget =
      approvedCalorieTarget ??
      (calorieMinimum !== null && calorieMaximum !== null
        ? (calorieMinimum + calorieMaximum) / 2
        : null);
    const nutritionMetrics: RingMetric[] = [
      {
        label: 'Calories',
        value: eventTotal('nutrition_calories'),
        target: calorieTarget,
        targetLabel:
          approvedCalorieTarget === null &&
          calorieMinimum !== null &&
          calorieMaximum !== null
            ? `${formatMetricNumber(calorieMinimum)}–${formatMetricNumber(calorieMaximum)}`
            : undefined,
        unit: 'kcal',
        color: '#f97316',
      },
      {
        label: 'Protein',
        value: eventTotal('nutrition_protein'),
        target: nutritionTarget('daily_protein'),
        unit: 'g',
        color: '#ec4899',
      },
      {
        label: 'Carbs',
        value: eventTotal('nutrition_carbohydrates'),
        target: nutritionTarget('daily_carbohydrates'),
        unit: 'g',
        color: '#3b82f6',
      },
      {
        label: 'Fat',
        value: eventTotal('nutrition_fat'),
        target: nutritionTarget('daily_fat'),
        unit: 'g',
        color: '#8b5cf6',
      },
      {
        label: 'Calcium',
        value: eventTotal('nutrition_calcium'),
        target: nutritionTarget('daily_calcium'),
        unit: 'mg',
        color: '#10b981',
      },
      {
        label: 'Fiber',
        value: eventTotal('nutrition_fiber'),
        target: nutritionTarget('daily_fiber'),
        unit: 'g',
        color: '#84cc16',
      },
    ];
    const simpleNutritionTasks = agentCheckIns('nutrition_coach').filter(
      (checkIn) => checkIn.input_required === false && !isAgentDelivery(checkIn),
    );
    const nutritionBinaryMetrics: BinaryMetric[] = simpleNutritionTasks.map(
      (checkIn) => ({
        label: shortTaskTitle(checkIn),
        complete:
          checkIn.status === 'responded' && checkIn.outcome !== 'partial',
      }),
    );

    const ouraMove = eventTotal('oura_active_calories');
    const ouraActivityScore = eventTotal('oura_activity_score');
    const whoopRecovery = eventTotal('whoop_recovery_score');
    const whoopStrain = eventTotal('whoop_day_strain');
    const whoopWorkoutMinutes = eventTotal('whoop_workout_minutes');
    const whoopSleepHours = eventTotal('whoop_sleep_hours');
    const sleepHours = whoopSleepHours || eventTotal('total_sleep_hours');
    const fitnessGoal = goals.find(
      (goal) => goal.owner_agent === 'fitness_coach',
    );
    const fitnessTarget = (key: string) => {
      const metric = fitnessGoal?.metrics.find((item) => item.key === key);
      if (!metric) return null;
      return (
        metric.target_value ?? metric.minimum_value ?? metric.maximum_value
      );
    };
    const workoutDone = taskWasDone('fitness_coach', 'workout or recovery day');
    const walkDone = taskWasDone('fitness_coach', 'evening walk with Kaju');
    const fitnessMetrics: RingMetric[] = [
      {
        label: 'Move',
        value: ouraMove,
        target: fitnessTarget('daily_active_calories'),
        unit: 'kcal',
        color: '#f43f5e',
      },
      {
        label: 'Exercise',
        value: whoopWorkoutMinutes || (workoutDone ? 30 : 0),
        target: 30,
        unit: 'min',
        color: '#06b6d4',
      },
      {
        label: 'Activity score',
        value: ouraActivityScore,
        target: 70,
        unit: 'score',
        color: '#84cc16',
      },
      {
        label: 'Sleep',
        value: sleepHours,
        target: 7,
        unit: 'hr',
        color: '#6366f1',
      },
      {
        label: 'Recovery',
        value: whoopRecovery,
        target: 100,
        unit: 'score',
        color: '#10b981',
      },
      {
        label: 'Day strain',
        value: whoopStrain,
        target: 21,
        unit: 'strain',
        color: '#f97316',
      },
      {
        label: 'Kaju walk',
        value: walkDone ? 1 : 0,
        target: 1,
        unit: 'walk',
        color: '#f59e0b',
      },
    ];

    const wellbeingKeys = [
      'mindset_accomplishments',
      'mindset_gratitude',
      'mindset_affirmations',
      'mindset_meditation_minutes',
      'mindset_one_action',
    ];
    const wakeUpSteps = wellbeingKeys.filter((key) => eventTotal(key) > 0).length;
    const wellbeingMetrics: BinaryMetric[] = [
      {
        label: 'Wake-up Routine',
        complete:
          wakeUpSteps === 5 ||
          taskWasDone('inner_wellbeing_guru', 'after-waking'),
      },
      {
        label: 'Meditation',
        complete: eventTotal('mindset_meditation_minutes') >= 10,
      },
      {
        label: 'Wind-down',
        complete: taskWasDone('inner_wellbeing_guru', 'before-sleep'),
      },
    ];

    const operationMetrics: RingMetric[] = [
      {
        label: 'Kaju play',
        value: taskWasDone('operations_manager', 'Play with Kaju') ? 5 : 0,
        target: 5,
        unit: 'min',
        color: '#65a30d',
      },
      {
        label: 'Kaju training',
        value: taskWasDone('operations_manager', 'Train Kaju') ? 10 : 0,
        target: 10,
        unit: 'min',
        color: '#14b8a6',
      },
      {
        label: 'Pumping',
        value: taskWasDone('operations_manager', 'pumping session') ? 1 : 0,
        target: 1,
        unit: 'session',
        color: '#f59e0b',
      },
      {
        label: 'Feeds by you',
        value: taskWasDone('operations_manager', 'personal feed log') ? 6 : 0,
        target: 6,
        unit: 'feeds',
        color: '#ec4899',
      },
    ];

    const archivistCheckIns = agentCheckIns('chief_archivist').filter(
      (item) => !isAgentDelivery(item),
    );
    const recordsForDay = knowledgeRecords.filter(
      (record) =>
        record.confirmed && dayKeyFromInstant(record.studied_at) === selectedDay,
    );
    const archivistScheduled =
      archivistCheckIns.length > 0 || recordsForDay.length > 0;
    const archivistMetrics: BinaryMetric[] = [
      {
        label: 'Study Debrief',
        complete: archivistCheckIns.some(
          (item) => item.status === 'responded' && item.outcome !== 'partial',
        ),
        unavailable: !archivistScheduled,
      },
      {
        label: 'Understanding Probe',
        complete: recordsForDay.some((record) =>
          record.probe_answers.some((answer) => answer.trim().length > 0),
        ),
        unavailable: !archivistScheduled,
      },
      {
        label: 'Knowledge Saved',
        complete: recordsForDay.length > 0,
        unavailable: !archivistScheduled,
      },
    ];

    const briefingDeliveries = agentCheckIns('briefing_intern').filter(
      isAgentDelivery,
    );
    const dailyBriefings = briefingDeliveries.filter(
      (item) => !item.prompt.toLowerCase().includes('weekly'),
    );
    const weeklyBriefings = briefingDeliveries.filter((item) =>
      item.prompt.toLowerCase().includes('weekly'),
    );
    const deliveryComplete = (items: CheckIn[]) =>
      items.some(
        (item) => item.status === 'delivered' || item.status === 'responded',
      );
    const briefingMetrics: BinaryMetric[] = [
      {
        label: 'Daily Briefing',
        complete: deliveryComplete(dailyBriefings),
        unavailable: dailyBriefings.length === 0,
      },
      {
        label: 'Briefing Reviewed',
        complete: eventTotal('briefing_reviewed') > 0,
        unavailable: dailyBriefings.length === 0,
      },
      {
        label: 'Weekly Synthesis',
        complete: deliveryComplete(weeklyBriefings),
        unavailable: weeklyBriefings.length === 0,
      },
    ];

    const simpleAgentMetrics = (agentId: string, color: string): RingMetric[] => [
      {
        label: 'Tasks',
        value: completedForAgent(agentId),
        target: agentCheckIns(agentId).filter((item) => !isAgentDelivery(item))
          .length,
        unit: 'done',
        color,
      },
    ];
    const agentName = (agentId: string) =>
      agents.find((agent) => agent.id === agentId)?.name || formatAgent(agentId);
    const dailyGroups: Array<{
      agentId: string;
      metrics: RingMetric[];
      binaryMetrics?: BinaryMetric[];
      tint: string;
      note?: string;
    }> = [
      {
        agentId: 'nutrition_coach',
        metrics: nutritionMetrics,
        binaryMetrics: nutritionBinaryMetrics,
        tint: 'from-orange-50 to-rose-50 dark:from-orange-950/35 dark:to-rose-950/25',
        note: nutritionMetrics.some((metric) => metric.target === null)
          ? 'Protein, carbohydrate, fat, fiber, and calcium totals are recorded, but their daily targets still need your approval.'
          : undefined,
      },
      {
        agentId: 'fitness_coach',
        metrics: fitnessMetrics,
        tint: 'from-cyan-50 to-indigo-50 dark:from-cyan-950/35 dark:to-indigo-950/25',
        note:
          !ouraMove && !sleepHours && !whoopRecovery
            ? 'WHOOP recovery, sleep, strain, and workouts will appear after you connect and sync WHOOP. Oura data remains supported.'
            : undefined,
      },
      {
        agentId: 'inner_wellbeing_guru',
        metrics: [],
        binaryMetrics: wellbeingMetrics,
        tint: 'from-rose-50 to-purple-50 dark:from-rose-950/35 dark:to-purple-950/25',
      },
      {
        agentId: 'operations_manager',
        metrics: operationMetrics,
        tint: 'from-lime-50 to-emerald-50 dark:from-lime-950/35 dark:to-emerald-950/25',
      },
      {
        agentId: 'knowledge_guru',
        metrics: simpleAgentMetrics('knowledge_guru', '#d97706'),
        tint: 'from-amber-50 to-yellow-50 dark:from-amber-950/35 dark:to-yellow-950/25',
      },
      {
        agentId: 'chief_archivist',
        metrics: [],
        binaryMetrics: archivistMetrics,
        tint: 'from-stone-100 to-amber-50 dark:from-stone-900/45 dark:to-amber-950/20',
      },
      {
        agentId: 'career_coach',
        metrics: simpleAgentMetrics('career_coach', '#2563eb'),
        tint: 'from-blue-50 to-sky-50 dark:from-blue-950/35 dark:to-sky-950/25',
      },
      {
        agentId: 'briefing_intern',
        metrics: [],
        binaryMetrics: briefingMetrics,
        tint: 'from-violet-50 to-fuchsia-50 dark:from-violet-950/35 dark:to-fuchsia-950/25',
      },
    ].filter(
      (group) =>
        agentCheckIns(group.agentId).length > 0 ||
        (group.agentId === 'chief_archivist' && recordsForDay.length > 0) ||
        dailyEvents.some(
          (event) =>
            event.domain === group.agentId ||
            event.domain === group.agentId.replace('_coach', '').replace('_guru', ''),
        ),
    );

    return (
      <>
        <DatedPageHeader
          title="Your Progress for the Day"
          selectedDay={selectedDay}
          displayDate={displayDate}
          viewingToday={viewingToday}
          onSelectDay={setSelectedDay}
          loading={loading}
          onRefresh={() => void loadDashboard()}
        />

        <div className="mt-5 rounded-3xl bg-gradient-to-br from-emerald-600 to-teal-700 p-5 text-white shadow-lg shadow-emerald-900/10">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-white/75">
            Your day
          </p>
          <div className="mt-1 flex items-end justify-between gap-4">
            <div>
              <p className="text-4xl font-bold tabular-nums">{dailyPercent}%</p>
              <p className="mt-1 text-sm text-white/80">
                {completedCount} / {totalToday} personal tasks complete
              </p>
            </div>
            <div className="rounded-2xl bg-white/15 px-3 py-2 text-right backdrop-blur">
              <p className="text-lg font-bold tabular-nums">
                {agentDeliveries.filter(
                  (item) => item.status === 'delivered' || item.status === 'responded',
                ).length}{' '}
                / {agentDeliveries.length}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/75">
                Agent deliveries
              </p>
            </div>
          </div>
          <Progress
            value={dailyPercent}
            className="mt-4 [&_[data-slot=progress-track]]:bg-white/20 [&_[data-slot=progress-indicator]]:bg-white"
          />
        </div>

        {goals.some(
          (goal) => goal.owner_agent === 'chief_finance_officer',
        ) && (
          <section className="mt-8">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Chief Finance Officer
            </p>
            <h2 className="mt-1 font-heading text-2xl font-semibold">
              Spending snapshot
            </h2>
            <Card className="mt-3 border-0 bg-gradient-to-br from-emerald-50 to-teal-50 ring-emerald-100 dark:from-emerald-950/35 dark:to-teal-950/25 dark:ring-emerald-900">
              <CardContent>
                {financeReport?.summaries.length ? (
                  <div className="space-y-4">
                    {financeReport.summaries.map((summary) => (
                      <div key={summary.currency}>
                        <p className="text-3xl font-bold tabular-nums text-emerald-800 dark:text-emerald-200">
                          {formatMoney(summary.net_spent, summary.currency)}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Net spent · {financeReport.purchase_count} confirmed purchase{financeReport.purchase_count === 1 ? '' : 's'}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {summary.categories.map((category) => (
                            <span key={category.category} className="rounded-full bg-white/75 px-3 py-1.5 text-xs font-semibold ring-1 ring-emerald-100 dark:bg-white/5 dark:ring-emerald-900">
                              {formatCategory(category.category)} · {formatMoney(category.amount, summary.currency)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <span className="flex size-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100">
                      <Landmark className="size-5" />
                    </span>
                    <div>
                      <p className="font-semibold">No confirmed purchases yet</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {financeReport?.processed_email_count ?? 0} email results recorded for this day.
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </section>
        )}

        <section className="mt-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Progress by agent
          </p>
          <div className="mt-3 space-y-5">
            {dailyGroups.map((group) => (
              <article
                key={group.agentId}
                className={`overflow-hidden rounded-[2rem] bg-gradient-to-br ${group.tint} p-5 shadow-sm ring-1 ring-black/5 dark:ring-white/10`}
              >
                <div className="flex items-center gap-3">
                  <AgentMark agentId={group.agentId} />
                  <div>
                    <h2 className="font-heading text-xl font-semibold">
                      {agentName(group.agentId)}
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {completedForAgent(group.agentId)} /{' '}
                      {agentCheckIns(group.agentId).filter(
                        (item) => !isAgentDelivery(item),
                      ).length}{' '}
                      personal tasks complete
                    </p>
                  </div>
                </div>
                {group.metrics.length > 0 && (
                  <>
                    <div className="mt-5 flex justify-center">
                      <ConcentricRings metrics={group.metrics} />
                    </div>
                    <MetricRows metrics={group.metrics} />
                  </>
                )}
                {group.binaryMetrics && group.binaryMetrics.length > 0 && (
                  <BinaryStatusTiles metrics={group.binaryMetrics} />
                )}
                {group.note && (
                  <p className="mt-3 rounded-2xl bg-white/55 px-3.5 py-3 text-xs leading-5 text-muted-foreground ring-1 ring-black/5 dark:bg-white/5 dark:ring-white/10">
                    {group.note}
                  </p>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="mt-9">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            High-level goals
          </p>
          <h2 className="mt-1 font-heading text-2xl font-semibold">
            Commitment cycles
          </h2>
          <div className="mt-4 space-y-3">
            {goals.map((goal) => {
              const due = cycleCheckIns.filter(
                (checkIn) => checkIn.goal_id === goal.id,
              );
              const completed = due.reduce((count, checkIn) => {
                if (
                  isAgentDelivery(checkIn) &&
                  (checkIn.status === 'delivered' || checkIn.status === 'responded')
                )
                  return count + 1;
                if (checkIn.status === 'responded')
                  return count + (checkIn.outcome === 'partial' ? 0.5 : 1);
                return count;
              }, 0);
              const goalPercent = due.length
                ? Math.round((completed / due.length) * 100)
                : 0;
              const totalCycleDays = Math.max(
                1,
                Math.round(
                  (localDateFromKey(dayKeyFromInstant(goal.review_at)).getTime() -
                    localDateFromKey(dayKeyFromInstant(goal.start_at)).getTime()) /
                    86_400_000,
                ) + 1,
              );
              const currentCycleDay = Math.min(
                totalCycleDays,
                Math.max(
                  1,
                  Math.round(
                    (localDateFromKey(selectedDay).getTime() -
                      localDateFromKey(dayKeyFromInstant(goal.start_at)).getTime()) /
                      86_400_000,
                  ) + 1,
                ),
              );
              return (
                <Card
                  key={goal.id}
                  size="sm"
                  className="border-0 bg-card shadow-sm ring-border"
                >
                  <CardContent>
                    <div className="flex items-start gap-3">
                      <AgentMark agentId={goal.owner_agent} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className="font-semibold leading-5">{goal.title}</p>
                          <span className="shrink-0 text-sm font-bold text-primary">
                            {goalPercent}%
                          </span>
                        </div>
                        <Progress value={goalPercent} className="mt-3 h-2" />
                        <div className="mt-2 flex justify-between gap-3 text-[11px] text-muted-foreground">
                          <span>
                            {formatMetricNumber(completed)} / {due.length} due actions complete
                          </span>
                          <span>
                            Day {currentCycleDay} / {totalCycleDays}
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>
      </>
    );
  };

  return (
    <>
      <main
        className={`min-h-dvh bg-background text-foreground ${view === 'check-in' && activeIsNutritionChat ? '' : 'pb-[calc(6.5rem+env(safe-area-inset-bottom))]'}`}
      >
        <div
          className={`mx-auto w-full max-w-md ${view === 'check-in' && activeIsNutritionChat ? 'px-0 pt-0' : 'px-5 pt-[max(1.25rem,env(safe-area-inset-top))]'}`}
        >
          {error && !(view === 'check-in' && activeIsNutritionChat) && (
            <div
              role="alert"
              className="mb-3 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}
          {view === 'today' && renderToday()}
          {view === 'check-in' && renderCheckIn()}
          {view === 'agents' && renderAgents()}
          {view === 'progress' && renderProgress()}
          {view === 'briefing' && renderBriefing()}
          {view === 'appointment-sync' && renderAppointmentSync()}
          {view === 'finance' && renderFinance()}
        </div>
      </main>
      {!(view === 'check-in' && activeIsNutritionChat) && (
        <BottomNav
          view={view}
          onChange={(next) => {
            setView(next);
            if (next === 'today' && view !== 'check-in') {
              setSelectedDay(todayKey());
            }
            if (next !== 'agents') setSelectedAgent(null);
          }}
        />
      )}
      <AlertDialog open={Boolean(logConfirmation)}>
        <AlertDialogContent className="w-[calc(100%-2rem)] rounded-3xl border border-border bg-card p-5 text-card-foreground shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogMedia className="rounded-full bg-emerald-100 text-emerald-800">
              <Check />
            </AlertDialogMedia>
            <AlertDialogTitle className="font-heading text-xl font-semibold">
              {logConfirmation?.title}
            </AlertDialogTitle>
            <AlertDialogDescription className="leading-6">
              {logConfirmation?.message}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-2 grid grid-cols-1 gap-2 bg-transparent p-4">
            <AlertDialogAction
              className="h-11 w-full rounded-xl"
              onClick={() =>
                closeLogConfirmation(
                  logConfirmation?.hasNextTask ? 'next' : 'today',
                )
              }
            >
              {logConfirmation?.hasNextTask ? 'Continue to next task' : 'Done'}
            </AlertDialogAction>
            {logConfirmation?.hasNextTask && (
              <Button
                variant="ghost"
                className="h-10 w-full rounded-xl"
                onClick={() => closeLogConfirmation('today')}
              >
                Back to today
              </Button>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {subtitle}
      </p>
      <h1 className="mt-1 font-heading text-3xl font-semibold tracking-[-0.035em]">
        {title}
      </h1>
    </header>
  );
}

function ConnectionCard({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="border-0 bg-card ring-border">
      <CardContent className="py-7 text-center">
        <ShieldCheck className="mx-auto size-8 text-primary" />
        <p className="mt-3 font-semibold">Connect to your private Life OS</p>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          The interface is ready, but the private service on your Mac is not
          responding.
        </p>
        <Button
          className="mt-4 rounded-full"
          variant="secondary"
          onClick={onRetry}
        >
          <RefreshCw /> Try again
        </Button>
      </CardContent>
    </Card>
  );
}

function BottomNav({
  view,
  onChange,
}: {
  view: View;
  onChange: (view: View) => void;
}) {
  const items: { label: string; value: View; icon: typeof House }[] = [
    { label: 'Plan', value: 'today', icon: House },
    { label: 'Progress', value: 'progress', icon: BarChart3 },
    { label: 'Agents', value: 'agents', icon: CircleUserRound },
  ];
  return (
    <nav
      className="fixed bottom-0 left-1/2 z-50 w-full max-w-md -translate-x-1/2 border-t border-border/70 bg-background/95 px-3 pb-[max(.7rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-12px_35px_-28px_var(--shadow-color)] backdrop-blur-xl"
      aria-label="Primary navigation"
    >
      <div className="grid grid-cols-3">
        {items.map(({ label, value, icon: Icon }) => {
          const active = value === view;
          return (
            <button
              key={value}
              onClick={() => onChange(value)}
              className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl text-[11px] font-medium ${active ? 'text-primary' : 'text-muted-foreground'}`}
            >
              <Icon className={`size-5 ${active ? 'stroke-[2.4]' : ''}`} />
              {label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
