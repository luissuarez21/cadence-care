export type Risk = "ok" | "monitor" | "escalate";

export type TimelineEntry = {
  day: string;
  date: string;
  type: "checkin" | "bp" | "symptom" | "med" | "fetal" | "flag";
  summary: string;
  detail?: string;
  flag?: boolean;
};

export type PatternAlert = {
  title: string;
  detail: string;
  severity: Risk;
};

export type Patient = {
  id: string;
  name: string;
  age: number;
  gestation: string;
  condition: string;
  risk: Risk;
  riskScore: number;
  riskRationale: string;
  lastCheckin: string;
  nextVisit: string;
  adherence: number;
  bpTrend: { day: string; sys: number; dia: number }[];
  timeline: TimelineEntry[];
  patterns: PatternAlert[];
  starters: string[];
  briefing: string;
};

export const patients: Patient[] = [
  {
    id: "maria-chen",
    name: "Maria Chen",
    age: 34,
    gestation: "29w 2d",
    condition: "Chronic hypertension · preeclampsia watch",
    risk: "escalate",
    riskScore: 0.86,
    riskRationale:
      "Two consecutive BP readings ≥140/90 within 30 minutes meet the care-plan escalation threshold. Headaches reported on 3 of the last 9 days with increasing frequency. Pattern is consistent with early preeclampsia per protocol.",
    lastCheckin: "12 min ago",
    nextVisit: "Thu, Jun 26 · 9:40 AM",
    adherence: 0.96,
    bpTrend: [
      { day: "D1", sys: 128, dia: 82 },
      { day: "D2", sys: 130, dia: 84 },
      { day: "D3", sys: 132, dia: 85 },
      { day: "D4", sys: 134, dia: 86 },
      { day: "D5", sys: 133, dia: 85 },
      { day: "D6", sys: 136, dia: 87 },
      { day: "D7", sys: 138, dia: 88 },
      { day: "D8", sys: 140, dia: 89 },
      { day: "D9", sys: 142, dia: 91 },
    ],
    timeline: [
      {
        day: "Today",
        date: "Jun 21 · 8:42 PM",
        type: "bp",
        summary: "BP 142/91 → repeat 140/90 (10 min later)",
        detail: "Both readings above care-plan threshold (140/90). Auto-flagged.",
        flag: true,
      },
      {
        day: "Today",
        date: "Jun 21 · 8:38 PM",
        type: "symptom",
        summary: "Reported dull frontal headache, 4/10",
        detail: "No vision changes. No epigastric pain. Took acetaminophen 500mg.",
      },
      {
        day: "Yesterday",
        date: "Jun 20 · 7:55 PM",
        type: "checkin",
        summary: "Check-in complete · no new symptoms",
      },
      {
        day: "Jun 19",
        date: "Jun 19 · 8:10 PM",
        type: "symptom",
        summary: "Headache mentioned, 3/10 · resolved with rest",
      },
      {
        day: "Jun 18",
        date: "Jun 18 · 7:48 PM",
        type: "fetal",
        summary: "Fetal movement normal · 10+ kicks in 1 hour",
      },
      {
        day: "Jun 17",
        date: "Jun 17 · 8:02 PM",
        type: "med",
        summary: "Labetalol taken on schedule · 7-day streak",
      },
      {
        day: "Jun 16",
        date: "Jun 16 · 7:30 PM",
        type: "symptom",
        summary: "Mild headache reported, 2/10",
      },
      {
        day: "Jun 15",
        date: "Jun 15 · 8:15 PM",
        type: "bp",
        summary: "BP 134/86 · within plan range",
      },
      {
        day: "Jun 14",
        date: "Jun 14 · 7:51 PM",
        type: "checkin",
        summary: "Check-in complete · no new symptoms",
      },
    ],
    patterns: [
      {
        title: "BP trending up over 4 days",
        detail: "Systolic +8 mmHg, diastolic +5 mmHg since Jun 17. Slope exceeds 2 mmHg/day.",
        severity: "escalate",
      },
      {
        title: "Recurring headaches",
        detail: "Reported on 3 of last 9 days, increasing intensity (2 → 3 → 4 /10).",
        severity: "monitor",
      },
      {
        title: "Excellent medication adherence",
        detail: "96% on-schedule across last 14 days. Labetalol 200mg BID.",
        severity: "ok",
      },
    ],
    starters: [
      "Ask about headache severity and visual symptoms in the last 48 hours.",
      "Consider 24-hour urine protein collection before next visit.",
      "Re-check BP manually before she leaves the exam room.",
      "Review home BP cuff technique — patient reported sitting/timing variation.",
    ],
    briefing:
      "Maria has completed 9 of 9 daily check-ins. BP has trended upward over the last 4 days and crossed the 140/90 threshold tonight on two consecutive readings. Headaches have recurred 3× in 9 days with rising intensity. Medication adherence is excellent. Pattern is consistent with early preeclampsia per the chronic-hypertension protocol on file.",
  },
  {
    id: "aisha-patel",
    name: "Aisha Patel",
    age: 31,
    gestation: "32w 0d",
    condition: "Gestational diabetes",
    risk: "monitor",
    riskScore: 0.52,
    riskRationale:
      "Fasting glucose elevated on 2 of last 5 mornings (98, 102 mg/dL). Otherwise within plan range. No symptoms reported.",
    lastCheckin: "2 hr ago",
    nextVisit: "Mon, Jun 30 · 10:20 AM",
    adherence: 0.88,
    bpTrend: [],
    timeline: [],
    patterns: [],
    starters: [],
    briefing: "",
  },
  {
    id: "rosa-mendez",
    name: "Rosa Mendez",
    age: 38,
    gestation: "27w 4d",
    condition: "Advanced maternal age · prior preeclampsia",
    risk: "monitor",
    riskScore: 0.41,
    riskRationale: "Sporadic swelling reported. BP stable. Adherence drifting (78%).",
    lastCheckin: "Yesterday",
    nextVisit: "Wed, Jun 25 · 2:15 PM",
    adherence: 0.78,
    bpTrend: [],
    timeline: [],
    patterns: [],
    starters: [],
    briefing: "",
  },
  {
    id: "jenna-okoro",
    name: "Jenna Okoro",
    age: 29,
    gestation: "34w 1d",
    condition: "Chronic hypertension",
    risk: "ok",
    riskScore: 0.12,
    riskRationale: "All readings within plan range. No symptoms. Adherence 100%.",
    lastCheckin: "3 hr ago",
    nextVisit: "Fri, Jun 27 · 11:00 AM",
    adherence: 1,
    bpTrend: [],
    timeline: [],
    patterns: [],
    starters: [],
    briefing: "",
  },
  {
    id: "lee-tran",
    name: "Lee Tran",
    age: 36,
    gestation: "30w 5d",
    condition: "Gestational hypertension",
    risk: "ok",
    riskScore: 0.18,
    riskRationale: "Stable BP. One missed check-in this week.",
    lastCheckin: "5 hr ago",
    nextVisit: "Tue, Jun 24 · 3:30 PM",
    adherence: 0.92,
    bpTrend: [],
    timeline: [],
    patterns: [],
    starters: [],
    briefing: "",
  },
  {
    id: "sam-rivera",
    name: "Sam Rivera",
    age: 27,
    gestation: "25w 3d",
    condition: "Gestational diabetes",
    risk: "ok",
    riskScore: 0.09,
    riskRationale: "Glucose well-controlled. No symptoms.",
    lastCheckin: "1 hr ago",
    nextVisit: "Mon, Jun 30 · 1:45 PM",
    adherence: 0.95,
    bpTrend: [],
    timeline: [],
    patterns: [],
    starters: [],
    briefing: "",
  },
];

export type Escalation = {
  id: string;
  patientId: string;
  patientName: string;
  receivedAt: string;
  headline: string;
  summary: string;
  vitals: string[];
  recommended: string;
  status: "new" | "acknowledged";
};

export const escalations: Escalation[] = [
  {
    id: "esc-001",
    patientId: "maria-chen",
    patientName: "Maria Chen",
    receivedAt: "12 min ago",
    headline: "BP 142/91 → 140/90 · headache 4/10",
    summary:
      "Two consecutive BP readings above the 140/90 care-plan threshold within 30 minutes. Frontal headache reported (4/10), no visual disturbance. Pattern consistent with early preeclampsia.",
    vitals: ["BP 142/91 · 8:42 PM", "BP 140/90 · 8:52 PM", "HR 88", "Headache 4/10"],
    recommended: "Contact within 4 hours · consider 24h urine protein · evaluate for early visit",
    status: "new",
  },
  {
    id: "esc-002",
    patientId: "aisha-patel",
    patientName: "Aisha Patel",
    receivedAt: "1 day ago",
    headline: "Fasting glucose 102 mg/dL · 2nd elevation this week",
    summary:
      "Second fasting glucose >100 mg/dL in 5 days. Patient reports compliance with diet plan. No other symptoms.",
    vitals: ["Glucose 102 · fasting", "Glucose 98 · fasting (Jun 19)"],
    recommended: "Routine follow-up · review diet log at next visit",
    status: "acknowledged",
  },
];
