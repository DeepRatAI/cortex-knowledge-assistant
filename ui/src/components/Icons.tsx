/**
 * Icons.tsx
 *
 * Centralized icon exports using Lucide React.
 * All icons used in the application should be imported from here
 * to ensure consistency and enable easy theming/replacement.
 *
 * Design decisions:
 * - Default size: 16px (suitable for inline with text)
 * - Default strokeWidth: 2 (balanced visibility)
 * - All icons inherit currentColor for CSS theming
 *
 * @see https://lucide.dev/icons/
 */

// Action icons
export {
  Pencil as EditIcon,
  Trash2 as DeleteIcon,
  Plus as AddIcon,
  Save as SaveIcon,
  X as CloseIcon,
  Check as CheckIcon,
  RotateCcw as RefreshIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  Copy as CopyIcon,
  Eye as ViewIcon,
  EyeOff as HideIcon,
  Search as SearchIcon,
  Filter as FilterIcon,
  MoreVertical as MoreIcon,
} from "lucide-react";

// Navigation icons
export {
  ChevronDown as ChevronDownIcon,
  ChevronUp as ChevronUpIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  ArrowLeft as BackIcon,
  ArrowRight as ForwardIcon,
  ExternalLink as ExternalLinkIcon,
  Home as HomeIcon,
  Menu as MenuIcon,
} from "lucide-react";

// Status icons
export {
  CheckCircle as SuccessIcon,
  XCircle as ErrorIcon,
  AlertTriangle as WarningIcon,
  Info as InfoIcon,
  HelpCircle as HelpIcon,
  Loader2 as SpinnerIcon,
  Clock as PendingIcon,
} from "lucide-react";

// Context/Domain icons
export {
  FileText as DocumentIcon,
  BookOpen as EducationalIcon,
  User as UserIcon,
  Users as UsersIcon,
  Building2 as OrganizationIcon,
  ClipboardList as DataIcon,
  MessageSquare as ChatIcon,
  Database as DatabaseIcon,
  Server as ServerIcon,
  Shield as SecurityIcon,
  Lock as LockIcon,
  Unlock as UnlockIcon,
  Key as KeyIcon,
} from "lucide-react";

// UI element icons
export {
  Settings as SettingsIcon,
  LogOut as LogoutIcon,
  LogIn as LoginIcon,
  Bell as NotificationIcon,
  Mail as MailIcon,
  Calendar as CalendarIcon,
  Folder as FolderIcon,
  File as FileIcon,
  Image as ImageIcon,
  Link as LinkIcon,
  Tag as TagIcon,
  Hash as HashIcon,
} from "lucide-react";

// Type export for consistent icon props
export type { LucideProps as IconProps } from "lucide-react";

/**
 * Default icon sizes for different contexts
 */
export const ICON_SIZES = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
} as const;

/**
 * Default stroke widths
 */
export const ICON_STROKES = {
  thin: 1,
  light: 1.5,
  regular: 2,
  bold: 2.5,
} as const;
