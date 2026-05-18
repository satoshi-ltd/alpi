import Activity from "./Activity.jsx";
import Icon from "./Icon.jsx";
import iconStyles from "./Icon.module.css";

export { default as Icon } from "./Icon.jsx";

// Canonical API: <Icon name="copy" size="lg" />.
// Named exports below are backward-compat wrappers; new code should use <Icon name=...>.

export const Search = (p) => <Icon name="search" {...p} />;
export const Plus = (p) => <Icon name="plus" {...p} />;
export const Arrow = (p) => <Icon name="arrow" {...p} />;
export const ArrowLeft = (p) => <Icon name="arrow-left" {...p} />;
export const ArrowRight = (p) => <Icon name="arrow-right" {...p} />;
export const Refresh = (p) => <Icon name="refresh" {...p} />;
export const SidebarI = (p) => <Icon name="sidebar" {...p} />;
export const Gear = (p) => <Icon name="gear" {...p} />;
export const Check = (p) => <Icon name="check" {...p} />;
export const X = (p) => <Icon name="x" {...p} />;
export const Pause = (p) => <Icon name="pause" {...p} />;
export const Play = (p) => <Icon name="play" {...p} />;
export const Copy = (p) => <Icon name="copy" {...p} />;
export const Help = (p) => <Icon name="help" {...p} />;
export const Cpu = (p) => <Icon name="cpu" {...p} />;
export const Wifi = (p) => <Icon name="wifi" {...p} />;
export const Globe = (p) => <Icon name="globe" {...p} />;
export const Sun = (p) => <Icon name="sun" {...p} />;
export const Moon = (p) => <Icon name="moon" {...p} />;
export const Auto = (p) => <Icon name="auto" {...p} />;
export const Trash = (p) => <Icon name="trash" {...p} />;
export const ChevDown = (p) => <Icon name="chev-down" {...p} />;
export const ChevRight = (p) => <Icon name="chev-right" {...p} />;
export const Send = (p) => <Icon name="send" {...p} />;
export const Dollar = (p) => <Icon name="dollar" {...p} />;
export const Spark = (p) => <Icon name="spark" {...p} />;
export const TagI = (p) => <Icon name="tag" {...p} />;
export const Folder = (p) => <Icon name="folder" {...p} />;
export const Eye = (p) => <Icon name="eye" {...p} />;
export const Mute = (p) => <Icon name="mute" {...p} />;
export const Archive = (p) => <Icon name="archive" {...p} />;
export const Bell = (p) => <Icon name="bell" {...p} />;

export const SearchIcon = Search;
export const PlusIcon = Plus;
export const ArrowUpIcon = Arrow;
export const ArrowLeftIcon = ArrowLeft;
export const ArrowRightIcon = ArrowRight;
export const RefreshIcon = Refresh;
export const SidebarIcon = SidebarI;
export const GearIcon = Gear;
export const CheckIcon = Check;
export const XIcon = X;
export const PauseIcon = Pause;
export const PlayIcon = Play;
export const CopyIcon = Copy;
export const HelpIcon = Help;
export const CpuIcon = Cpu;
export const WifiIcon = Wifi;
export const GlobeIcon = Globe;
export const SunIcon = Sun;
export const MoonIcon = Moon;
export const AutoIcon = Auto;
export const TrashIcon = Trash;
export const ChevDownIcon = ChevDown;
export const ChevRightIcon = ChevRight;
export const SendIcon = Send;
export const DollarIcon = Dollar;
export const SparkIcon = Spark;
export const TagIcon = TagI;
export const FolderIcon = Folder;
export const EyeIcon = Eye;
export const MuteIcon = Mute;
export const ArchiveIcon = Archive;
export const BellIcon = Bell;
export const SkipIcon = (p) => <Icon name="skip" {...p} />;
export const StopIcon = (p) => <Icon name="stop" {...p} />;
export const VolumeIcon = (p) => <Icon name="volume" {...p} />;
export const EditIcon = (p) => <Icon name="edit" {...p} />;
export const CaretIcon = (p) => <Icon name="caret" size={12} color="var(--ink-3)" {...p} />;
export const BackIcon = (p) => <Icon name="back" size={16} {...p} />;
export const SidebarOpenIcon = (p) => <Icon name="sidebar-open" size={16} {...p} />;
export const SidebarCloseIcon = (p) => <Icon name="sidebar-close" size={16} {...p} />;
export const UndoIcon = (p) => <Icon name="undo" {...p} />;
export const QuestionIcon = (p) => <Icon name="question" {...p} />;
export const AlpiIcon = (p) => <Icon name="alpi" size={12} {...p} />;

export function SpinnerIcon({ className = "", style, ...rest }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      className={`ds-icon ds-spin ${className}`.trim()}
      style={style}
      aria-hidden="true"
      {...rest}
    >
      <circle cx="8" cy="8" r="6" strokeDasharray="22 38" />
    </svg>
  );
}

export function PinIcon({ filled = false, className = "", style, ...rest }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`ds-icon ${className}`.trim()}
      style={{
        width: 13,
        height: 13,
        stroke: "currentColor",
        fill: filled ? "currentColor" : "none",
        strokeWidth: 1.5,
        strokeLinecap: "round",
        strokeLinejoin: "round",
        ...style,
      }}
      {...rest}
    >
      <path d="M9.5 2.5l4 4-2 .5-2.5 2.5.5 3-2.5-2.5L3 13l3-4-2.5-2.5 3 .5L9 4l.5-1.5z" />
    </svg>
  );
}

export const PinOffIcon = (p) => <PinIcon filled={false} {...p} />;

export function LocalConnectionIcon(p) {
  return <Icon name="local-connection" size={14} {...p} />;
}

export function RemoteConnectionIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className} name="alpi">
      <svg viewBox="0 0 24 24" fill="none">
        <rect width="20" height="8" x="2" y="14" rx="2" stroke="currentColor" strokeWidth="2" />
        <path d="M6.01 18H6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M10.01 18H10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M15 10v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M17.84 7.17a4 4 0 0 0-5.66 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M20.66 4.34a8 8 0 0 0-11.31 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </Icon>
  );
}

export function StatusIcon({ kind, className = "", style }) {
  if (kind === "done") {
    return (
      <Check
        className={className}
        style={{ width: 13, height: 13, strokeWidth: 2, color: "var(--c-success)", ...style }}
      />
    );
  }
  if (kind === "paused") {
    return (
      <Pause
        className={className}
        style={{ width: 11, height: 11, strokeWidth: 2, color: "var(--ink-4)", ...style }}
      />
    );
  }
  if (kind === "error") {
    return (
      <span
        className={className}
        aria-hidden
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: "var(--c-danger)",
          display: "inline-block",
          ...style,
        }}
      />
    );
  }
  if (kind === "working") {
    return <Activity size="sm" className={className} style={style} />;
  }
  return (
    <span
      className={className}
      aria-hidden
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        border: "1.5px solid var(--ink-4)",
        display: "inline-block",
        ...style,
      }}
    />
  );
}

export const Alpaca = (p) => (
  <svg viewBox="0 0 40 40" {...p}>
    <circle cx="20" cy="22" r="11" fill="currentColor" />
    <rect x="10" y="6" width="6" height="11" rx="3" fill="currentColor" />
    <rect x="24" y="6" width="6" height="11" rx="3" fill="currentColor" />
    <circle cx="16" cy="21" r="1.4" fill="var(--bg-pane)" />
    <circle cx="24" cy="21" r="1.4" fill="var(--bg-pane)" />
  </svg>
);
export const AlpacaIcon = Alpaca;

export const I = {
  Search, Plus, Arrow, ArrowLeft, ArrowRight, Refresh, Sidebar: SidebarI,
  Gear, Check, X, Pause, Play, Copy, Help, Cpu, Wifi, Globe, Sun, Moon,
  Trash, ChevDown, ChevRight, Send, Dollar, Spark, Tag: TagI, Folder, Eye,
  MuteIcon: Mute, Archive, Bell, Alpaca,
};
