import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { VideoFeed } from "@/lib/api";

interface FeedDeleteDialogProps {
  feed: VideoFeed | null;
  isDeleting: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}

export function FeedDeleteDialog({
  feed,
  isDeleting,
  onConfirm,
  onOpenChange,
}: FeedDeleteDialogProps) {
  return (
    <AlertDialog open={feed !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove Feed</AlertDialogTitle>
          <AlertDialogDescription>
            {feed
              ? `Remove ${feed.name} from the dashboard and backend registry? This stops using the source until you add it again.`
              : "Remove this feed from the dashboard and backend registry?"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? "Removing..." : "Remove Feed"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}