import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ErrorState({ title, message }: { title: string; message: string }) {
  return (
    <Card className="border-red-400/20 bg-red-950/20">
      <CardContent className="flex items-start gap-3 p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 text-red-300" />
        <div>
          <div className="text-sm font-medium text-red-100">{title}</div>
          <div className="mt-1 text-sm text-red-200/70">{message}</div>
        </div>
      </CardContent>
    </Card>
  );
}
