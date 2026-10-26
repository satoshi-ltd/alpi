import { Easing } from 'react-native-reanimated';

import { motion } from '../theme/tokens';

export const EASE_ENTER = Easing.bezier(...motion.easeEnter);
export const EASE_EXIT = Easing.bezier(...motion.easeExit);
