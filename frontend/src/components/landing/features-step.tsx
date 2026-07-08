"use client";

import {
  Globe,
  Cpu,
  Code2,
  Download,
  ArrowBigRight,
  type LucideIcon,
} from "lucide-react";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

const iconMap: Record<string, LucideIcon> = {
  Globe,
  Cpu,
  Code2,
  Download,
};

interface FeaturesStepProps {
  label?: string;
  title: string;
  description: string;
  items: Array<{
    title: string;
    description: string;
    icon: string;
  }>;
  className?: string;
}

export function FeaturesStep({
  label,
  title,
  description,
  items,
  className,
}: FeaturesStepProps) {
  return (
    <section className={cn("py-16 md:py-24", className)}>
      <div className="m-4 rounded-[2rem]">
        <div className="relative container">
          <ScrollAnimation>
            <div className="mx-auto max-w-2xl text-center">
              {label && <span className="text-primary">{label}</span>}
              <h2 className="text-foreground mt-4 text-4xl font-semibold">
                {title}
              </h2>
              <p className="text-muted-foreground mt-4 text-lg text-balance">
                {description}
              </p>
            </div>
          </ScrollAnimation>

          <ScrollAnimation delay={0.2}>
            <div className="mt-20 grid gap-12 md:grid-cols-4">
              {items.map((item, idx) => {
                const Icon = iconMap[item.icon] || Globe;
                return (
                  <div className="space-y-6" key={idx}>
                    <div className="text-center">
                      <span className="mx-auto flex size-6 items-center justify-center rounded-full bg-zinc-500/15 text-sm font-medium">
                        {idx + 1}
                      </span>
                      <div className="relative">
                        <div className="mx-auto my-6 w-fit">
                          <Icon className="h-6 w-6" />
                        </div>
                        {idx < items.length - 1 && (
                          <ArrowBigRight className="fill-muted stroke-primary absolute inset-y-0 right-0 my-auto mt-1 hidden translate-x-[150%] drop-shadow md:block" />
                        )}
                      </div>
                      <h3 className="text-foreground mb-4 text-lg font-semibold">
                        {item.title}
                      </h3>
                      <p className="text-muted-foreground text-balance">
                        {item.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollAnimation>
        </div>
      </div>
    </section>
  );
}
