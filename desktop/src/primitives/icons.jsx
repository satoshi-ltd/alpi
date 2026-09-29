import Activity from "./Activity.jsx";
import Dot from "./Dot.jsx";
import Icon from "./Icon.jsx";
import iconStyles from "./Icon.module.css";

export { default as Icon } from "./Icon.jsx";

// Canonical API: <Icon name="copy" size="lg" />.
// Named exports below are backward-compat wrappers; new code should use <Icon name=...>.

const Search = (p) => <Icon name="search" {...p} />;
const Plus = (p) => <Icon name="plus" {...p} />;
const Arrow = (p) => <Icon name="arrow" {...p} />;
const ArrowLeft = (p) => <Icon name="arrow-left" {...p} />;
const Refresh = (p) => <Icon name="refresh" {...p} />;
const Gear = (p) => <Icon name="gear" {...p} />;
const Check = (p) => <Icon name="check" {...p} />;
const X = (p) => <Icon name="x" {...p} />;
const Pause = (p) => <Icon name="pause" {...p} />;
const Play = (p) => <Icon name="play" {...p} />;
export const Power = (p) => <Icon name="power" {...p} />;
const Copy = (p) => <Icon name="copy" {...p} />;
const Cpu = (p) => <Icon name="cpu" {...p} />;
const Server = (p) => <Icon name="server" {...p} />;
const Globe = (p) => <Icon name="globe" {...p} />;
const Sun = (p) => <Icon name="sun" {...p} />;
const Moon = (p) => <Icon name="moon" {...p} />;
const Auto = (p) => <Icon name="sun-moon" {...p} />;
const Trash = (p) => <Icon name="trash" {...p} />;
const ChevDown = (p) => <Icon name="chev-down" {...p} />;
const ChevRight = (p) => <Icon name="chev-right" {...p} />;
const Send = (p) => <Icon name="send" {...p} />;
const SendToChat = (p) => <Icon name="arrow-right-to-line" {...p} />;
const Blocks = (p) => <Icon name="blocks" {...p} />;
const Sparkle = (p) => <Icon name="sparkle" {...p} />;
const Wrench = (p) => <Icon name="wrench" {...p} />;
const Eye = (p) => <Icon name="eye" {...p} />;
const Lock = (p) => <Icon name="lock" {...p} />;
export const PaperclipIcon = (p) => <Icon name="paperclip" {...p} />;
export const LinkIcon = (p) => <Icon name="link" {...p} />;
export const FileIcon = (p) => <Icon name="file" {...p} />;
export const FileTextIcon = (p) => <Icon name="file-text" {...p} />;
export const FileCodeIcon = (p) => <Icon name="file-code" {...p} />;
const Mute = (p) => <Icon name="mute" {...p} />;
const Volume = (p) => <Icon name="volume" {...p} />;
const Archive = (p) => <Icon name="archive" {...p} />;
const Bell = (p) => <Icon name="bell" {...p} />;

export const SearchIcon = Search;
export const PlusIcon = Plus;
export const ArrowUpIcon = Arrow;
export const ArrowLeftIcon = ArrowLeft;
export const RefreshIcon = Refresh;
export const GearIcon = Gear;
export const CheckIcon = Check;
export const XIcon = X;
const Download = (p) => <Icon name="download" {...p} />;
export const DownloadIcon = Download;
export const PauseIcon = Pause;
export const PlayIcon = Play;
export const CopyIcon = Copy;
export const CpuIcon = Cpu;
export const ServerIcon = Server;
export const GlobeIcon = Globe;
export const SunIcon = Sun;
export const MoonIcon = Moon;
export const AutoIcon = Auto;
export const TrashIcon = Trash;
export const ChevDownIcon = ChevDown;
export const ChevRightIcon = ChevRight;
export const SendIcon = Send;
export const SendToChatIcon = SendToChat;
export const BlocksIcon = Blocks;
export const SparkleIcon = Sparkle;
export const EyeIcon = Eye;
export const LockIcon = Lock;
export const WrenchIcon = Wrench;
export const MuteIcon = Mute;
export const ArchiveIcon = Archive;
export const BellIcon = Bell;
export const SkipIcon = (p) => <Icon name="skip" {...p} />;
export const StopIcon = (p) => <Icon name="stop" {...p} />;
export const VolumeIcon = Volume;
export const EditIcon = (p) => <Icon name="edit" {...p} />;
export const CaretIcon = (p) => <Icon name="caret" size={12} color="var(--ink-3)" {...p} />;
export const BackIcon = (p) => <Icon name="arrow-left" size={16} {...p} />;
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

export const PinIcon = (p) => <Icon name="pin" {...p} />;
export const PinOffIcon = (p) => <Icon name="pin-off" {...p} />;

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
    return <Dot pulse color="var(--c-accent, var(--accent))" className={className} style={style} />;
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

const Alpaca = (p) => (
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
  Search, Plus, Arrow, ArrowLeft, Refresh,
  Gear, Check, X, Pause, Play, Power, Copy, Cpu, Server, Globe, Sun, Moon,
  Trash, ChevDown, ChevRight, Send, Blocks, Sparkle, Wrench,
  MuteIcon: Mute, Volume, Archive, Bell, Alpaca,
};
