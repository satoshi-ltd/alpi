const PATHS = [
  "M 512,508 L 195,555 L 169,640 L 299,770 L 351,782 Z",
  "M 714,653 L 526,517 L 368,786 L 503,813 Z",
  "M 545,211 L 530,499 L 724,639 L 684,367 Z",
  "M 165,658 L 123,811 L 71,1065 L 283,779 Z",
  "M 713,676 L 612,752 L 593,897 L 622,1065 Z",
  "M 300,787 L 294,789 L 234,874 L 290,1064 L 345,803 L 343,797 Z",
  "M 561,201 L 560,205 L 670,331 L 675,333 L 730,215 L 621,169 Z",
  "M 595,764 L 508,831 L 551,1092 L 560,1051 Z",
  "M 178,553 L 78,638 L 119,746 L 123,743 Z",
  "M 783,246 L 746,222 L 693,330 L 699,329 L 781,293 L 783,291 Z",
  "M 595,70 L 592,74 L 552,189 L 566,183 L 608,159 L 597,75 Z",
  "M 684,89 L 682,89 L 628,150 L 626,153 L 627,155 L 670,174 L 673,172 L 685,92 Z",
];

export default function AlpiSilhouette({ color, style, className }) {
  return (
    <svg
      width="72"
      height="72"
      viewBox="71 70 712 1022"
      role="img"
      aria-label="alpi"
      className={className}
      style={{ color: color || "currentColor", display: "block", ...style }}
    >
      {PATHS.map((d, i) => (
        <path key={i} d={d} fill="currentColor" />
      ))}
    </svg>
  );
}
