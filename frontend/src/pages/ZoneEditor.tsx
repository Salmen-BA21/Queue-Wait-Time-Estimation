import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2, Edit, CheckCircle, XCircle } from "lucide-react";
import { useState, useRef, useCallback, useEffect } from "react";

interface Point {
  x: number;
  y: number;
}

interface Zone {
  id: string;
  name: string;
  points: Point[];
  color: string;
}

const COLORS = ["hsl(187 82% 53%)", "hsl(258 73% 76%)", "hsl(160 60% 45%)", "hsl(38 92% 50%)"];

export default function ZoneEditor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedCamera, setSelectedCamera] = useState("entrance-a");
  const [zones, setZones] = useState<Zone[]>([
    {
      id: "z1",
      name: "Queue Area 1",
      points: [
        { x: 0.1, y: 0.2 },
        { x: 0.5, y: 0.15 },
        { x: 0.55, y: 0.7 },
        { x: 0.15, y: 0.75 },
      ],
      color: COLORS[0],
    },
  ]);
  const [drawing, setDrawing] = useState(false);
  const [currentPoints, setCurrentPoints] = useState<Point[]>([]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Background grid
    ctx.strokeStyle = "rgba(148,163,184,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i < w; i += 40) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke();
    }
    for (let i = 0; i < h; i += 40) {
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke();
    }

    // Draw existing zones
    zones.forEach((zone) => {
      if (zone.points.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(zone.points[0].x * w, zone.points[0].y * h);
      zone.points.forEach((p, i) => { if (i > 0) ctx.lineTo(p.x * w, p.y * h); });
      ctx.closePath();
      ctx.fillStyle = zone.color.replace(")", " / 0.15)").replace("hsl(", "hsla(");
      ctx.fill();
      ctx.strokeStyle = zone.color;
      ctx.lineWidth = 2;
      ctx.stroke();
      zone.points.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, 4, 0, Math.PI * 2);
        ctx.fillStyle = zone.color;
        ctx.fill();
      });
    });

    // Draw current points
    if (currentPoints.length > 0) {
      ctx.beginPath();
      ctx.moveTo(currentPoints[0].x * w, currentPoints[0].y * h);
      currentPoints.forEach((p, i) => { if (i > 0) ctx.lineTo(p.x * w, p.y * h); });
      ctx.strokeStyle = COLORS[zones.length % COLORS.length];
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);
      currentPoints.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, 5, 0, Math.PI * 2);
        ctx.fillStyle = COLORS[zones.length % COLORS.length];
        ctx.fill();
      });
    }
  }, [zones, currentPoints]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const resize = () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      draw();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);
    return () => ro.disconnect();
  }, [draw]);

  useEffect(() => { draw(); }, [draw]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / canvas.width;
    const y = (e.clientY - rect.top) / canvas.height;
    setCurrentPoints((prev) => [...prev, { x, y }]);
  };

  const finishZone = () => {
    if (currentPoints.length < 3) return;
    const newZone: Zone = {
      id: `z${Date.now()}`,
      name: `Zone ${zones.length + 1}`,
      points: currentPoints,
      color: COLORS[zones.length % COLORS.length],
    };
    setZones((prev) => [...prev, newZone]);
    setCurrentPoints([]);
    setDrawing(false);
  };

  const deleteZone = (id: string) => {
    setZones((prev) => prev.filter((z) => z.id !== id));
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Zone Editor</h1>
            <p className="text-sm text-muted-foreground">Define queue areas within camera views</p>
          </div>
          <Select value={selectedCamera} onValueChange={setSelectedCamera}>
            <SelectTrigger className="w-48 bg-card border-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="entrance-a">Entrance A</SelectItem>
              <SelectItem value="entrance-b">Entrance B</SelectItem>
              <SelectItem value="checkout-1">Checkout 1</SelectItem>
              <SelectItem value="checkout-2">Checkout 2</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Canvas */}
          <div className="lg:col-span-2">
            <div ref={containerRef} className="relative aspect-video rounded-lg border border-border bg-card overflow-hidden cursor-crosshair">
              <canvas ref={canvasRef} onClick={handleCanvasClick} className="absolute inset-0" />
              {/* Controls overlay */}
              <div className="absolute bottom-3 left-3 flex gap-2">
                {!drawing ? (
                  <Button size="sm" onClick={() => { setDrawing(true); setCurrentPoints([]); }}>
                    Draw Zone
                  </Button>
                ) : (
                  <>
                    <Button size="sm" onClick={finishZone} disabled={currentPoints.length < 3} className="bg-success hover:bg-success/90 text-success-foreground">
                      <CheckCircle className="h-3 w-3 mr-1" /> Finish ({currentPoints.length} pts)
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => { setDrawing(false); setCurrentPoints([]); }}>
                      <XCircle className="h-3 w-3 mr-1" /> Cancel
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Zone list */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Defined Zones</h2>
            {zones.length === 0 && (
              <p className="text-sm text-muted-foreground">No zones defined. Click "Draw Zone" to start.</p>
            )}
            {zones.map((zone) => (
              <div key={zone.id} className="rounded-lg border border-border bg-card p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-3 w-3 rounded-full" style={{ backgroundColor: zone.color }} />
                  <div>
                    <p className="text-sm font-medium text-foreground">{zone.name}</p>
                    <p className="text-xs text-muted-foreground">{zone.points.length} points</p>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground">
                    <Edit className="h-3 w-3" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => deleteZone(zone.id)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
            {zones.length > 0 && (
              <div className="text-xs text-muted-foreground flex items-center gap-1.5 mt-2">
                <CheckCircle className="h-3 w-3 text-success" />
                All zones valid (≥3 points)
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
