import { AppShell } from "@/components/shell/app-shell";
import { MotionProvider } from "@/components/shell/motion-provider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <MotionProvider>
      <AppShell>{children}</AppShell>
    </MotionProvider>
  );
}
