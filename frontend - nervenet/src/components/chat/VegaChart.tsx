import React, { useEffect, useRef, useState } from "react";
import vegaEmbed from "vega-embed";
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  ArrowRight, 
  Activity,
  Download,
  Image,
  FileSpreadsheet,
  BarChart3,
  LineChart,
  AreaChart
} from "lucide-react";

interface KPI {
  title: string;
  value: string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  style?: "default" | "success" | "danger" | "warning";
}

interface VegaChartProps {
  specString: string;
  onSendMessage?: (prompt: string, attachments: any[]) => void;
}

export const VegaChart: React.FC<VegaChartProps> = ({ specString, onSendMessage }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<any>(null);
  
  const [error, setError] = useState<string | null>(null);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [title, setTitle] = useState<string | null>(null);
  const [subtitle, setSubtitle] = useState<string | null>(null);
  const [footer, setFooter] = useState<string | null>(null);
  
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(true);
  const [markOverride, setMarkOverride] = useState<string | null>(null);

  // 1. Detect light/dark theme changes to re-color the chart dynamically
  useEffect(() => {
    const checkTheme = () => {
      setIsDarkMode(document.documentElement.classList.contains("dark"));
    };
    
    checkTheme();
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  // 2. Monitor wrapper width changes to keep charts responsive
  useEffect(() => {
    if (!wrapperRef.current) return;
    
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    
    resizeObserver.observe(wrapperRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // 3. Render and bind the Vega-Lite specification
  useEffect(() => {
    if (!containerRef.current || containerWidth === 0) return;

    let parsedSpec: any;
    try {
      parsedSpec = JSON.parse(specString);
    } catch (e) {
      setError("Failed to parse Vega-Lite JSON specification");
      return;
    }

    // Extract metadata
    if (parsedSpec.usermeta) {
      setKpis(parsedSpec.usermeta.kpis || []);
      setTitle(parsedSpec.usermeta.title || null);
      setSubtitle(parsedSpec.usermeta.subtitle || null);
      setFooter(parsedSpec.usermeta.footer || null);
    } else {
      setKpis([]);
      setTitle(null);
      setSubtitle(null);
      setFooter(null);
    }

    // Create a copy of the spec to modify properties safely
    const renderSpec = JSON.parse(JSON.stringify(parsedSpec));
    
    // Override chart mark if user clicked a view switcher option
    if (markOverride) {
      if (renderSpec.vconcat && Array.isArray(renderSpec.vconcat)) {
        renderSpec.vconcat.forEach((child: any) => { if (child.mark) child.mark = markOverride; });
      } else if (renderSpec.hconcat && Array.isArray(renderSpec.hconcat)) {
        renderSpec.hconcat.forEach((child: any) => { if (child.mark) child.mark = markOverride; });
      } else if (renderSpec.mark) {
        renderSpec.mark = markOverride;
      }
    }

    // Fit dynamic boundaries
    renderSpec.autosize = { type: "fit", contains: "padding" };
    
    if (!renderSpec.hconcat && !renderSpec.concat) {
      renderSpec.width = "container";
    } else if (renderSpec.hconcat && Array.isArray(renderSpec.hconcat)) {
      const count = renderSpec.hconcat.length;
      const gap = 16;
      const totalGap = gap * (count - 1);
      const childWidth = Math.floor((containerWidth - totalGap) / count);
      renderSpec.hconcat.forEach((child: any) => {
        child.width = Math.max(childWidth, 100);
      });
    }

    // Theme values dependent on Light/Dark Mode
    const themeBackground = isDarkMode ? "#0d0d11" : "#ffffff";
    const axisColor = isDarkMode ? "#27272a" : "#e4e4e7";
    const gridColor = isDarkMode ? "#1e1e24" : "#f4f4f5";
    const labelColor = isDarkMode ? "#a1a1aa" : "#71717a";
    const titleColor = isDarkMode ? "#ffffff" : "#09090b";

    const options: any = {
      actions: false,
      theme: "dark",
      config: {
        background: themeBackground,
        autosize: { type: "fit", contains: "padding" },
        title: { 
          color: titleColor, 
          fontSize: 13, 
          font: "Inter, system-ui, sans-serif",
          anchor: "start",
          dy: -10
        },
        style: {
          cell: { stroke: "transparent" }
        },
        line: {
          interpolate: "monotone",
          strokeWidth: 3,
          point: { size: 36, filled: true, fill: "#ffffff" }
        },
        area: {
          interpolate: "monotone",
          point: { size: 36, filled: true, fill: "#ffffff" }
        },
        bar: {
          cornerRadiusTopLeft: 6,
          cornerRadiusTopRight: 6,
          binSpacing: 2
        },
        axis: {
          domainColor: axisColor,
          gridColor: gridColor,
          gridOpacity: 0.8,
          labelColor: labelColor,
          titleColor: labelColor,
          tickColor: axisColor,
          labelFont: "Inter, system-ui, sans-serif",
          titleFont: "Inter, system-ui, sans-serif",
          labelFontSize: 9,
          titleFontSize: 10
        },
        legend: {
          labelColor: labelColor,
          titleColor: labelColor,
          labelFont: "Inter, system-ui, sans-serif",
          titleFont: "Inter, system-ui, sans-serif",
          labelFontSize: 9,
          titleFontSize: 10
        },
        view: { stroke: "transparent" },
        mark: {
          color: "#06b6d4", // Cyan base
          invalid: null
        }
      },
      width: "container",
      height: 220
    };

    containerRef.current.innerHTML = "";
    setError(null);

    vegaEmbed(containerRef.current, renderSpec, options)
      .then(({ view }) => {
        viewRef.current = view;

        // Drill-down click listener to query database dynamically
        view.addEventListener("click", (event, item) => {
          if (item && item.datum && onSendMessage) {
            const datum = item.datum;
            const queryParts: string[] = [];
            
            if (datum.consumer_id) {
              queryParts.push(`for Consumer ID <//UID-${datum.consumer_id}//>`);
            } else if (datum.consumer_no) {
              queryParts.push(`for Consumer No <//UID-${datum.consumer_no}//>`);
            }
            
            if (datum.bill_month) {
              queryParts.push(`for billing month ${datum.bill_month}`);
            } else if (datum.reading_month) {
              queryParts.push(`for reading month ${datum.reading_month}`);
            } else if (datum.month) {
              queryParts.push(`for month ${datum.month}`);
            }
            
            if (datum.bill_status) {
              queryParts.push(`with billing status "${datum.bill_status}"`);
            } else if (datum.reading_status) {
              queryParts.push(`with reading status "${datum.reading_status}"`);
            } else if (datum.category) {
              queryParts.push(`for category "${datum.category}"`);
            }

            if (queryParts.length > 0) {
              const promptText = `Analyze records ${queryParts.join(" ")} in detail and summarize the key findings.`;
              onSendMessage(promptText, []);
            }
          }
        });
      })
      .catch((err) => {
        console.error("Vega-Lite rendering error:", err);
        setError("Invalid Vega-Lite specification details");
      });
  }, [specString, containerWidth, isDarkMode, markOverride, onSendMessage]);

  // Recursively extract dataset values for CSV download
  const extractDataValues = (spec: any): any[] => {
    if (spec.data?.values) return spec.data.values;
    if (spec.vconcat && Array.isArray(spec.vconcat)) {
      for (const child of spec.vconcat) {
        const v = extractDataValues(child);
        if (v && v.length > 0) return v;
      }
    }
    if (spec.hconcat && Array.isArray(spec.hconcat)) {
      for (const child of spec.hconcat) {
        const v = extractDataValues(child);
        if (v && v.length > 0) return v;
      }
    }
    return [];
  };

  const handleExportCSV = () => {
    let parsed: any;
    try {
      parsed = JSON.parse(specString);
    } catch { return; }
    
    const values = extractDataValues(parsed);
    if (!values || values.length === 0) return;
    
    const headers = Object.keys(values[0]).filter(k => k !== "key" && !k.startsWith("vega"));
    const csvRows = [
      headers.join(","),
      ...values.map(row => headers.map(header => JSON.stringify(row[header] ?? "")).join(","))
    ];
    
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(title || "chart").toLowerCase().replace(/\s+/g, "_")}_data.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSaveImage = async () => {
    if (!viewRef.current) return;
    try {
      const url = await viewRef.current.toImageURL("png");
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(title || "chart").toLowerCase().replace(/\s+/g, "_")}.png`;
      a.click();
    } catch (err) {
      console.error("Save image failed:", err);
    }
  };

  const renderTrendIcon = (trend?: "up" | "down" | "neutral") => {
    if (trend === "up") return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
    if (trend === "down") return <TrendingDown className="w-3.5 h-3.5 text-rose-400" />;
    return <ArrowRight className="w-3.5 h-3.5 text-zinc-400" />;
  };

  const getStyleClasses = (style?: "default" | "success" | "danger" | "warning") => {
    switch (style) {
      case "success":
        return {
          card: "border-emerald-500/20 bg-emerald-500/5",
          badge: "bg-emerald-500/10 text-emerald-400"
        };
      case "danger":
        return {
          card: "border-rose-500/20 bg-rose-500/5",
          badge: "bg-rose-500/10 text-rose-400"
        };
      case "warning":
        return {
          card: "border-amber-500/20 bg-amber-500/5",
          badge: "bg-amber-500/10 text-amber-400"
        };
      default:
        return {
          card: "border-zinc-800/80 bg-zinc-900/30",
          badge: "bg-zinc-800/80 text-zinc-400"
        };
    }
  };

  return (
    <div className="w-full my-4 dark:bg-[#0c0c0e] bg-gray-50 border border-zinc-800/60 rounded-2xl shadow-2xl flex flex-col gap-6 overflow-hidden">
      
      {/* ⚠️ Tooltip Custom Styling Injection */}
      <style>{`
        .vg-tooltip {
          background: rgba(12, 12, 16, 0.9) !important;
          backdrop-filter: blur(8px) !important;
          border: 1px solid rgba(255, 255, 255, 0.08) !important;
          border-radius: 10px !important;
          color: #e4e4e7 !important;
          font-family: Inter, system-ui, sans-serif !important;
          font-size: 10px !important;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6) !important;
          padding: 8px 12px !important;
        }
        .vg-tooltip th {
          color: #a1a1aa !important;
          text-align: left !important;
          padding-right: 14px !important;
          font-weight: 600 !important;
        }
        .vg-tooltip td {
          color: #ffffff !important;
          font-weight: 500 !important;
        }
      `}</style>

      {/* Dashboard Title & Header */}
      {title && (
        <div className="flex flex-col gap-1 border-b border-zinc-800/40 pb-4 pt-6 px-6 select-none">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 text-white">
              <div className="p-1.5 bg-cyan-500/10 rounded-lg text-cyan-400">
                <Activity className="w-4 h-4" />
              </div>
              <h3 className="text-base font-bold tracking-tight">{title}</h3>
            </div>
            
            {/* View switcher mark override button bar */}
            <div className="flex items-center gap-1 bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-0.5 select-none">
              <button 
                onClick={() => setMarkOverride(markOverride === "bar" ? null : "bar")}
                className={`p-1.5 rounded-md hover:bg-zinc-800 transition-colors ${markOverride === "bar" ? "bg-zinc-800 text-cyan-400" : "text-muted-foreground hover:text-white"}`}
                title="Bar Chart View"
              >
                <BarChart3 className="w-3.5 h-3.5" />
              </button>
              <button 
                onClick={() => setMarkOverride(markOverride === "line" ? null : "line")}
                className={`p-1.5 rounded-md hover:bg-zinc-800 transition-colors ${markOverride === "line" ? "bg-zinc-800 text-cyan-400" : "text-muted-foreground hover:text-white"}`}
                title="Line Chart View"
              >
                <LineChart className="w-3.5 h-3.5" />
              </button>
              <button 
                onClick={() => setMarkOverride(markOverride === "area" ? null : "area")}
                className={`p-1.5 rounded-md hover:bg-zinc-800 transition-colors ${markOverride === "area" ? "bg-zinc-800 text-cyan-400" : "text-muted-foreground hover:text-white"}`}
                title="Area Chart View"
              >
                <AreaChart className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          {subtitle && (
            <p className="text-xs text-muted-foreground/80 pl-9 font-medium tracking-wide">
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* KPI Cards Grid */}
      {kpis.length > 0 && (
        <div className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 px-6 ${!title ? "pt-6" : ""}`}>
          {kpis.map((kpi, i) => {
            const styles = getStyleClasses(kpi.style);
            return (
              <div
                key={i}
                className={`p-4 rounded-xl border flex flex-col gap-1 transition-all duration-300 hover:scale-[1.02] ${styles.card}`}
              >
                <span className="text-[9px] font-bold text-muted-foreground/85 uppercase tracking-wider">
                  {kpi.title}
                </span>
                <span className="text-lg font-extrabold dark:text-white text-zinc-900 tracking-tight">
                  {kpi.value}
                </span>
                {kpi.change && (
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${styles.badge}`}>
                      {kpi.change}
                    </span>
                    {kpi.trend && renderTrendIcon(kpi.trend)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Responsive Wrapper for Vega Chart */}
      <div ref={wrapperRef} className={`px-6 pb-2 ${!title && kpis.length === 0 ? "pt-6" : ""}`}>
        <div ref={containerRef} className="w-full vega-embed-container [&>.vega-embed]:w-full" />
      </div>

      {/* Control Utility Toolbar (Export Actions) */}
      <div className="flex items-center justify-between border-t border-zinc-800/40 py-4 px-6 select-none bg-zinc-950/20">
        {footer ? (
          <span className="text-[10px] font-medium text-muted-foreground/40 tracking-wider">
            {footer}
          </span>
        ) : (
          <div />
        )}
        
        <div className="flex items-center gap-2">
          <button 
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900/40 hover:bg-zinc-900 text-[10px] font-bold text-muted-foreground hover:text-white transition-all"
            title="Download dataset as CSV file"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
          <button 
            onClick={handleSaveImage}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900/40 hover:bg-zinc-900 text-[10px] font-bold text-muted-foreground hover:text-white transition-all"
            title="Save chart layout as PNG image"
          >
            <Image className="w-3.5 h-3.5" />
            <span>Save PNG</span>
          </button>
        </div>
      </div>
    </div>
  );
};
