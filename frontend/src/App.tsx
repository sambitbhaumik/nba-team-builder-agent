import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { jsPDF } from "jspdf";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  GripVertical,
  Lightbulb,
  PanelRight,
  Send,
  Trash2,
  WandSparkles,
} from "lucide-react";

import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "./components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./components/ui/dialog";
import { Input } from "./components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Textarea } from "./components/ui/textarea";
import { cn } from "./lib/utils";

type Player = {
  id: string;
  name: string;
  position: "PG" | "SG" | "SF" | "PF" | "C";
  team: string;
  fpg: number;
  value: number;
  tags: string[];
  steals: number;
  threes: number;
  rebounds: number;
};

type RosterSlot = {
  id: string;
  label: string;
  group: "starter" | "bench";
  playerId?: string;
};

type SavedTeam = {
  id: string;
  name: string;
  createdAt: string;
  budgetUsed: number;
  roster: RosterSlot[];
};

type TraceStep = {
  action: string;
  status: "success" | "fail" | "pending";
  detail?: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  trace?: TraceStep[];
  knowledgeHint?: string;
};

const initialPlayers: Player[] = [
  { id: "p1", name: "Stephen Curry", position: "PG", team: "GSW", fpg: 45.7, value: 30.5, tags: ["3PT", "OFFENSE"], steals: 1.1, threes: 4.8, rebounds: 4.4 },
  { id: "p2", name: "Damian Lillard", position: "PG", team: "MIL", fpg: 41.3, value: 27.6, tags: ["3PT", "CLUTCH"], steals: 1.0, threes: 4.2, rebounds: 4.3 },
  { id: "p3", name: "Jrue Holiday", position: "PG", team: "BOS", fpg: 32.4, value: 21.6, tags: ["DEFENSE"], steals: 1.4, threes: 2.1, rebounds: 4.6 },
  { id: "p4", name: "Mikal Bridges", position: "SF", team: "BKN", fpg: 34.2, value: 22.8, tags: ["DEFENSE", "IRONMAN"], steals: 1.2, threes: 2.3, rebounds: 4.8 },
  { id: "p5", name: "Anthony Davis", position: "PF", team: "LAL", fpg: 44.0, value: 29.3, tags: ["DEFENSE", "RIM"], steals: 1.3, threes: 0.2, rebounds: 12.2 },
  { id: "p6", name: "Jaren Jackson Jr.", position: "PF", team: "MEM", fpg: 36.4, value: 24.3, tags: ["DEFENSE", "BLOCKS"], steals: 1.0, threes: 1.6, rebounds: 6.8 },
  { id: "p7", name: "Bam Adebayo", position: "C", team: "MIA", fpg: 37.8, value: 25.2, tags: ["DEFENSE", "PLAYMAKER"], steals: 1.1, threes: 0.2, rebounds: 9.5 },
  { id: "p8", name: "Klay Thompson", position: "SG", team: "DAL", fpg: 29.1, value: 19.4, tags: ["3PT"], steals: 0.8, threes: 3.9, rebounds: 3.5 },
  { id: "p9", name: "Anunoby", position: "SF", team: "NYK", fpg: 30.5, value: 20.3, tags: ["DEFENSE"], steals: 1.6, threes: 2.4, rebounds: 4.7 },
  { id: "p10", name: "Brook Lopez", position: "C", team: "MIL", fpg: 28.0, value: 18.7, tags: ["DEFENSE", "BLOCKS"], steals: 0.6, threes: 1.5, rebounds: 6.4 },
  { id: "p11", name: "Desmond Bane", position: "SG", team: "MEM", fpg: 33.0, value: 22.0, tags: ["3PT"], steals: 0.9, threes: 3.1, rebounds: 4.5 },
  { id: "p12", name: "Alex Caruso", position: "SG", team: "CHI", fpg: 24.5, value: 16.3, tags: ["DEFENSE"], steals: 1.7, threes: 1.4, rebounds: 3.3 },
  { id: "p13", name: "Derrick White", position: "SG", team: "BOS", fpg: 31.6, value: 21.1, tags: ["DEFENSE", "3PT"], steals: 1.0, threes: 2.7, rebounds: 4.2 },
  { id: "p14", name: "Donovan Mitchell", position: "SG", team: "CLE", fpg: 39.5, value: 26.3, tags: ["3PT", "OFFENSE"], steals: 1.5, threes: 3.2, rebounds: 4.4 },
  { id: "p15", name: "Draymond Green", position: "PF", team: "GSW", fpg: 29.9, value: 19.9, tags: ["DEFENSE"], steals: 1.2, threes: 1.0, rebounds: 7.5 },
];

const rosterTemplate: RosterSlot[] = [
  { id: "s1", label: "PG", group: "starter" },
  { id: "s2", label: "SG", group: "starter" },
  { id: "s3", label: "SF", group: "starter" },
  { id: "s4", label: "PF", group: "starter" },
  { id: "s5", label: "C", group: "starter" },
  { id: "b1", label: "Bench 1", group: "bench" },
  { id: "b2", label: "Bench 2", group: "bench" },
  { id: "b3", label: "Bench 3", group: "bench" },
  { id: "b4", label: "Bench 4", group: "bench" },
  { id: "b5", label: "Bench 5", group: "bench" },
  { id: "b6", label: "Bench 6", group: "bench" },
  { id: "b7", label: "Bench 7", group: "bench" },
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "m0",
      role: "assistant",
      content:
        "What kind of roster do you want to build? Tell me your budget, play style, and any player preferences.",
    },
  ]);
  const [userInput, setUserInput] = useState("");
  const [roster, setRoster] = useState<RosterSlot[]>(rosterTemplate);
  const [placingSlots, setPlacingSlots] = useState<string[]>([]);
  const [savedTeams, setSavedTeams] = useState<SavedTeam[]>([
    { id: "team-1", name: "Defensive Anchors", createdAt: "2026-01-28 18:21", budgetUsed: 142.5, roster: rosterTemplate },
    { id: "team-2", name: "3PT Storm", createdAt: "2026-01-24 20:14", budgetUsed: 148.9, roster: rosterTemplate },
  ]);
  const [teamName, setTeamName] = useState("My Team");
  const [pendingDelete, setPendingDelete] = useState<SavedTeam | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({});

  const [leftWidth, setLeftWidth] = useState(50);
  const [rightPanelVisible, setRightPanelVisible] = useState(true);
  const dragging = useRef(false);
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const playerById = useMemo(
    () => Object.fromEntries(initialPlayers.map((p) => [p.id, p])),
    []
  );

  const rosterPlayers = roster
    .map((slot) => (slot.playerId ? playerById[slot.playerId] : null))
    .filter(Boolean) as Player[];

  const budgetUsed = rosterPlayers.reduce((sum, p) => sum + p.value, 0);
  const budgetTotal = 150;
  const budgetRatio = Math.min(budgetUsed / budgetTotal, 1);
  const hasRoster = rosterPlayers.length > 0;

  const toggleTrace = (id: string) =>
    setExpandedTraces((prev) => ({ ...prev, [id]: !prev[id] }));

  const autoFillRoster = () => {
    const recommended = [...initialPlayers].sort((a, b) => b.fpg - a.fpg).slice(0, 12);
    const updated = roster.map((slot, i) => ({ ...slot, playerId: recommended[i]?.id }));
    setRoster(updated);
    setPlacingSlots(updated.map((s) => s.id));
    setTimeout(() => setPlacingSlots([]), 800);
  };

  const handleDrop = (slotId: string, playerId: string, fromSlotId?: string) => {
    setRoster((prev) => {
      const updated = prev.map((s) => ({ ...s }));
      const targetIdx = updated.findIndex((s) => s.id === slotId);
      if (targetIdx === -1) return prev;
      
      // Get the player currently in the target slot (if any)
      const targetPlayerId = updated[targetIdx].playerId;
      
      // Place the dragged player in the target slot
      updated[targetIdx].playerId = playerId;
      
      // Handle the source slot
      if (fromSlotId) {
        const fromIdx = updated.findIndex((s) => s.id === fromSlotId);
        if (fromIdx !== -1 && fromIdx !== targetIdx) {
          // If target slot had a player, swap them; otherwise clear the source slot
          updated[fromIdx].playerId = targetPlayerId;
        }
      }
      return updated;
    });
  };

  const handleSend = () => {
    if (!userInput.trim()) return;
    const userMsg: Message = { id: `u-${Date.now()}`, role: "user", content: userInput.trim() };
    const trace: TraceStep[] = [
      { action: "Parse user intent", status: "success", detail: "budget=150, priorities=3PT+defense" },
      { action: "Fetch NBA API data", status: "success", detail: "450 active players loaded" },
      { action: "Compute FPG + dollar values", status: "success" },
      { action: "Filter by criteria", status: "success", detail: "Defensive wings with 3PT > 36%" },
      { action: "Optimize roster", status: "success" },
    ];
    const assistantMsg: Message = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content:
        "I've built a roster prioritizing 3-point shooting and defense within your $150 budget. Review it in the panel on the right, then save or adjust as needed.",
      trace,
      knowledgeHint: "Based on your history, I weighted high-steal players more heavily.",
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setUserInput("");
    autoFillRoster();
  };

  const saveRoster = () => {
    const newTeam: SavedTeam = {
      id: `team-${Date.now()}`,
      name: teamName || "Untitled",
      createdAt: new Date().toLocaleString(),
      budgetUsed,
      roster,
    };
    setSavedTeams((prev) => [newTeam, ...prev]);
  };

  const deleteTeam = (team: SavedTeam) => {
    setSavedTeams((prev) => prev.filter((t) => t.id !== team.id));
    setPendingDelete(null);
  };

  const loadTeam = (team: SavedTeam) => setRoster(team.roster);

  const downloadCsv = () => {
    const rows = [
      ["Slot", "Player", "Position", "Team", "FPG", "Value"],
      ...roster.map((slot) => {
        const p = slot.playerId ? playerById[slot.playerId] : null;
        return [slot.label, p?.name ?? "-", p?.position ?? "-", p?.team ?? "-", p?.fpg?.toFixed(1) ?? "-", p?.value?.toFixed(1) ?? "-"];
      }),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "roster.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadPdf = () => {
    const doc = new jsPDF();
    doc.setFontSize(14);
    doc.text("Team Roster", 14, 16);
    doc.setFontSize(10);
    let y = 28;
    roster.forEach((slot) => {
      const p = slot.playerId ? playerById[slot.playerId] : null;
      doc.text(`${slot.label}: ${p?.name ?? "-"} | ${p?.team ?? "-"} | $${p?.value?.toFixed(1) ?? "-"}`, 14, y);
      y += 7;
    });
    doc.text(`Budget: $${budgetUsed.toFixed(1)} / $${budgetTotal}`, 14, y + 4);
    doc.save("roster.pdf");
  };

  const onMouseDown = useCallback(() => {
    dragging.current = true;
  }, []);

  const onMouseUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return;
    const container = e.currentTarget as HTMLElement;
    const rect = container.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setLeftWidth(Math.max(25, Math.min(75, pct)));
  }, []);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () => chatEndRef.current?.scrollIntoView({ behavior: "smooth" });

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setSelectedSlotId(null);
      }
    };

    if (selectedSlotId) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [selectedSlotId]);

  const handlePlayerCardClick = (e: React.MouseEvent, slotId: string) => {
    // Prevent drag from starting when clicking
    e.stopPropagation();
    setSelectedSlotId(selectedSlotId === slotId ? null : slotId);
  };

  const handleReplacePlayer = (slotId: string) => {
    const slot = roster.find((s) => s.id === slotId);
    if (slot?.playerId) {
      const player = playerById[slot.playerId];
      if (player) {
        setUserInput(`replace ${player.name}`);
        setSelectedSlotId(null);
        // Focus the chat input
        setTimeout(() => {
          const textarea = document.querySelector('textarea[placeholder*="Build me a team"]') as HTMLTextAreaElement;
          textarea?.focus();
        }, 0);
      }
    }
  };

  const handleRemovePlayer = (slotId: string) => {
    setRoster((prev) => prev.map((s) => (s.id === slotId ? { ...s, playerId: undefined } : s)));
    setSelectedSlotId(null);
  };

  return (
    <div
      className="flex h-screen select-none"
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      {/* LEFT: Chat */}
      <section
        className="flex flex-col border-r border-border bg-card relative"
        style={{ width: hasRoster && rightPanelVisible ? `${leftWidth}%` : "100%" }}
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-4">
          <h1 className="text-lg font-semibold tracking-tight">Sport Agent</h1>
          <Badge className="bg-primary text-primary-foreground">$150 Budget</Badge>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("max-w-[90%]", msg.role === "user" ? "ml-auto" : "")}>
              {msg.trace && (
                <button
                  onClick={() => toggleTrace(msg.id)}
                  className="mb-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  {expandedTraces[msg.id] ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  Show reasoning
                </button>
              )}

              {msg.trace && expandedTraces[msg.id] && (
                <div className="mb-2 space-y-1 rounded-md border border-border bg-muted/50 p-3 text-xs">
                  {msg.trace.map((step, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span
                        className={cn(
                          "mt-1 h-2 w-2 shrink-0 rounded-full",
                          step.status === "success" && "bg-green-500",
                          step.status === "fail" && "bg-red-500",
                          step.status === "pending" && "bg-yellow-500"
                        )}
                      />
                      <span>
                        {step.action}
                        {step.detail && <span className="text-muted-foreground"> — {step.detail}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div
                className={cn(
                  "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground"
                )}
              >
                {msg.content}
              </div>

              {msg.knowledgeHint && (
                <div className="mt-2 flex items-start gap-2 rounded-md border border-accent/40 bg-accent/10 px-3 py-2 text-xs text-accent">
                  <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{msg.knowledgeHint}</span>
                </div>
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="border-t border-border p-4">
          <div className="flex gap-2 items-center">
            <Textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                  scrollToBottom();
                }
              }}
              placeholder="Build me a team with $150..."
              className="min-h-[48px] resize-none rounded-2xl"
            />
            <Button 
              size="icon" 
              onClick={() => { handleSend(); scrollToBottom(); }}
              className="rounded-2xl"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Toggle button when right panel is hidden */}
        {hasRoster && !rightPanelVisible && (
          <button
            onClick={() => setRightPanelVisible(true)}
            className="absolute right-4 top-1/2 -translate-y-1/2 z-10 rounded-full bg-primary text-primary-foreground p-2 shadow-lg hover:bg-primary/90 transition-colors"
            aria-label="Show roster panel"
          >
            <PanelRight className="h-5 w-5" />
          </button>
        )}
      </section>

      {/* RESIZE HANDLE */}
      {hasRoster && rightPanelVisible && (
        <div
          onMouseDown={onMouseDown}
          className="resize-handle flex w-2 items-center justify-center bg-border hover:bg-primary/30"
        >
          <GripVertical className="h-5 w-5 text-muted-foreground" />
        </div>
      )}

      {/* RIGHT: Roster + Artifacts */}
      {hasRoster && rightPanelVisible && (
        <section className="flex flex-1 flex-col overflow-hidden bg-background">
          <header className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold">Roster Builder</h2>
              <p className="text-xs text-muted-foreground">
                ${budgetUsed.toFixed(1)} / ${budgetTotal} used
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={autoFillRoster}>
                <WandSparkles className="mr-1 h-3.5 w-3.5" />
                Auto-fill
              </Button>
              <Dialog>
                <DialogTrigger asChild>
                  <Button size="sm">Save</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Save roster?</DialogTitle>
                    <DialogDescription>Give your roster a name.</DialogDescription>
                  </DialogHeader>
                  <Input value={teamName} onChange={(e) => setTeamName(e.target.value)} />
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="secondary">Cancel</Button>
                    </DialogClose>
                    <DialogClose asChild>
                      <Button onClick={saveRoster}>Confirm</Button>
                    </DialogClose>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setRightPanelVisible(false)}
                className="h-8 w-8"
                aria-label="Hide roster panel"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Budget bar */}
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${budgetRatio * 100}%` }}
              />
            </div>

            {/* Starters */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Starting Five</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-5 gap-2">
                {roster
                  .filter((s) => s.group === "starter")
                  .map((slot) => {
                    const p = slot.playerId ? playerById[slot.playerId] : null;
                    return (
                      <div
                        key={slot.id}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          const pid = e.dataTransfer.getData("playerId");
                          const from = e.dataTransfer.getData("fromSlotId");
                          if (pid) handleDrop(slot.id, pid, from || undefined);
                        }}
                        className={cn(
                          "relative flex flex-col items-center justify-center rounded-lg border border-dashed p-3 text-center transition",
                          placingSlots.includes(slot.id) && "ring-2 ring-primary"
                        )}
                      >
                        <span className="text-[10px] uppercase text-muted-foreground">{slot.label}</span>
                        {p ? (
                          <div
                            draggable
                            onDragStart={(e) => {
                              e.dataTransfer.setData("playerId", p.id);
                              e.dataTransfer.setData("fromSlotId", slot.id);
                              setSelectedSlotId(null); // Close menu when dragging
                            }}
                            onClick={(e) => handlePlayerCardClick(e, slot.id)}
                            className="mt-1 cursor-grab w-full"
                          >
                            <p className="text-xs font-semibold leading-tight">{p.name}</p>
                            <p className="text-[10px] text-muted-foreground">${p.value.toFixed(1)}</p>
                          </div>
                        ) : (
                          <span className="mt-1 text-[10px] text-muted-foreground">Empty</span>
                        )}
                        {selectedSlotId === slot.id && p && (
                          <div
                            ref={menuRef}
                            className="absolute top-full left-0 mt-1 z-50 min-w-[140px] rounded-md border bg-popover shadow-md p-1"
                          >
                            <button
                              onClick={() => handleReplacePlayer(slot.id)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground transition-colors"
                            >
                              <WandSparkles className="h-3.5 w-3.5" />
                              Replace
                            </button>
                            <button
                              onClick={() => handleRemovePlayer(slot.id)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground transition-colors text-destructive"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              Remove
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </CardContent>
            </Card>

            {/* Bench */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Bench</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-4 gap-2">
                {roster
                  .filter((s) => s.group === "bench")
                  .map((slot) => {
                    const p = slot.playerId ? playerById[slot.playerId] : null;
                    return (
                      <div
                        key={slot.id}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          const pid = e.dataTransfer.getData("playerId");
                          const from = e.dataTransfer.getData("fromSlotId");
                          if (pid) handleDrop(slot.id, pid, from || undefined);
                        }}
                        className={cn(
                          "relative flex flex-col items-center justify-center rounded-lg border border-dashed p-2 text-center transition",
                          placingSlots.includes(slot.id) && "ring-2 ring-primary"
                        )}
                      >
                        <span className="text-[10px] uppercase text-muted-foreground">{slot.label}</span>
                        {p ? (
                          <div
                            draggable
                            onDragStart={(e) => {
                              e.dataTransfer.setData("playerId", p.id);
                              e.dataTransfer.setData("fromSlotId", slot.id);
                              setSelectedSlotId(null); // Close menu when dragging
                            }}
                            onClick={(e) => handlePlayerCardClick(e, slot.id)}
                            className="mt-1 cursor-grab w-full"
                          >
                            <p className="text-xs font-semibold leading-tight">{p.name}</p>
                            <p className="text-[10px] text-muted-foreground">${p.value.toFixed(1)}</p>
                          </div>
                        ) : (
                          <span className="mt-1 text-[10px] text-muted-foreground">Empty</span>
                        )}
                        {selectedSlotId === slot.id && p && (
                          <div
                            ref={menuRef}
                            className="absolute top-full left-0 mt-1 z-50 min-w-[140px] rounded-md border bg-popover shadow-md p-1"
                          >
                            <button
                              onClick={() => handleReplacePlayer(slot.id)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground transition-colors"
                            >
                              <WandSparkles className="h-3.5 w-3.5" />
                              Replace
                            </button>
                            <button
                              onClick={() => handleRemovePlayer(slot.id)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground transition-colors text-destructive"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              Remove
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </CardContent>
            </Card>

            {/* Artifacts */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Artifacts</CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="download">
                  <TabsList className="mb-3">
                    <TabsTrigger value="download">Download</TabsTrigger>
                    <TabsTrigger value="saved">Saved Teams</TabsTrigger>
                  </TabsList>
                  <TabsContent value="download" className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={downloadCsv}>
                      <Download className="mr-1 h-3.5 w-3.5" />
                      CSV
                    </Button>
                    <Button variant="outline" size="sm" onClick={downloadPdf}>
                      <Download className="mr-1 h-3.5 w-3.5" />
                      PDF
                    </Button>
                  </TabsContent>
                  <TabsContent value="saved" className="space-y-2">
                    {savedTeams.map((team) => (
                      <div
                        key={team.id}
                        className="flex items-center justify-between rounded-md border border-border bg-card p-3"
                      >
                        <div>
                          <p className="text-sm font-medium">{team.name}</p>
                          <p className="text-xs text-muted-foreground">{team.createdAt}</p>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="secondary" size="sm" onClick={() => loadTeam(team)}>
                            Load
                          </Button>
                          <Dialog>
                            <DialogTrigger asChild>
                              <Button variant="destructive" size="icon" className="h-8 w-8" onClick={() => setPendingDelete(team)}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Delete "{pendingDelete?.name}"?</DialogTitle>
                                <DialogDescription>This cannot be undone.</DialogDescription>
                              </DialogHeader>
                              <DialogFooter>
                                <DialogClose asChild>
                                  <Button variant="secondary">Cancel</Button>
                                </DialogClose>
                                <DialogClose asChild>
                                  <Button variant="destructive" onClick={() => pendingDelete && deleteTeam(pendingDelete)}>
                                    Delete
                                  </Button>
                                </DialogClose>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </div>
                      </div>
                    ))}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </section>
      )}
    </div>
  );
}
