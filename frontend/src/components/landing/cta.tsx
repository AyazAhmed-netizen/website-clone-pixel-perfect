"use client";

import Link from "next/link";
import { Zap, Github, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

const iconMap: Record<string, LucideIcon> = {
  Zap,
  Github,
};

interface CtaProps {
  id?: string;
  title: string;
  description: string;
  buttons?: Array<{
    title: string;
    url: string;
    variant?: "default" | "outline";
    icon?: string;
    target?: string;
  }>;
  className?: string;
}

export function Cta({ id, title, description, buttons, className }: CtaProps) {
  return (
    <section id={id} className={cn("py-16 md:py-24", className)}>
      <div className="container">
        <div className="text-center">
          <ScrollAnimation>
            <h2 className="text-4xl font-semibold text-balance lg:text-5xl">
              {title}
            </h2>
          </ScrollAnimation>
          <ScrollAnimation delay={0.15}>
            <p
              className="mt-4 text-muted-foreground"
              dangerouslySetInnerHTML={{ __html: description }}
            />
          </ScrollAnimation>

          <ScrollAnimation delay={0.3}>
            <div className="mt-12 flex flex-wrap justify-center gap-4">
              {buttons?.map((button, idx) => {
                const Icon = button.icon ? iconMap[button.icon] : null;
                return (
                  <Button
                    asChild
                    variant={button.variant || "default"}
                    key={idx}
                  >
                    <Link href={button.url} target={button.target || "_self"}>
                      {Icon && <Icon className="mr-2 h-4 w-4" />}
                      <span>{button.title}</span>
                    </Link>
                  </Button>
                );
              })}
            </div>
          </ScrollAnimation>
        </div>
      </div>
    </section>
  );
}
