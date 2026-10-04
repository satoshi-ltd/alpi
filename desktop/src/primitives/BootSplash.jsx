import { ALPACA_FOLD, FOLD_SIZES } from "../../../common/folds.mjs";
import Fold from "./Fold.jsx";
import styles from "./BootSplash.module.css";

export default function BootSplash({ message = "Connecting to daemon…" }) {
  return (
    <div className={styles.root}>
      <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} className={styles.glyph} />
      <span className={styles.msg}>{message}</span>
    </div>
  );
}
