"use client";

import { useState } from "react";
import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import {
  Monitor,
  MousePointerClick,
  HelpCircle,
  Code,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";
import { SmartIcon } from "@/components/common";

const iconMap: Record<string, LucideIcon> = {
  Monitor,
  MousePointerClick,
  HelpCircle,
  Code,
};

interface FeaturesAccordionProps {
  id?: string;
  label?: string;
  title: string;
  description: string;
  items: Array<{
    title: string;
    description: string;
    icon: string;
    image?: {
      src: string;
      alt: string;
    };
  }>;
  className?: string;
}

export function FeaturesAccordion({
  id,
  label,
  title,
  description,
  items,
  className,
}: FeaturesAccordionProps) {
  const [activeItem, setActiveItem] = useState<number>(0);

  return (
    <section
      id={id}
      className={cn("overflow-x-hidden py-16 md:py-24", className)}
    >
      <div className="container space-y-8 md:space-y-16 lg:space-y-20">
        <ScrollAnimation>
          <div className="mx-auto max-w-4xl text-center text-balance">
            {label && (
              <span className="text-primary text-sm font-medium mb-2 block">
                {label}
              </span>
            )}
            <h2 className="text-foreground mb-4 text-3xl font-semibold tracking-tight md:text-4xl">
              {title}
            </h2>
            <p className="text-muted-foreground mb-6 md:mb-12 lg:mb-16">
              {description}
            </p>
          </div>
        </ScrollAnimation>

        <div className="grid gap-12 md:grid-cols-2 lg:gap-20">
          <ScrollAnimation delay={0.1} direction="left">
            <div className="w-full space-y-2">
              {items.map((item, idx) => {
                const Icon = iconMap[item.icon] || Monitor;
                const isActive = activeItem === idx;

                return (
                  <div
                    key={idx}
                    className={cn(
                      "rounded-xl border transition-all cursor-pointer",
                      isActive
                        ? "bg-card shadow-sm border-border"
                        : "border-transparent hover:bg-muted/50"
                    )}
                  >
                    <button
                      onClick={() => setActiveItem(idx)}
                      className="flex w-full items-center justify-between px-6 py-4 text-left"
                    >
                      <div className="flex items-center gap-3">
                        <Icon className="h-5 w-5 flex-shrink-0" />
                        <span className="font-medium">{item.title}</span>
                      </div>
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 transition-transform flex-shrink-0",
                          isActive && "rotate-180"
                        )}
                      />
                    </button>
                    <AnimatePresence>
                      {isActive && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <p className="px-6 pb-4 text-muted-foreground text-sm">
                            {item.description}
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </ScrollAnimation>

          <ScrollAnimation delay={0.2} direction="right">
            <div className="bg-background relative flex overflow-hidden rounded-3xl border p-2">
              <div className="absolute inset-y-0 right-0 w-16 border-l bg-[repeating-linear-gradient(-45deg,var(--color-border),var(--color-border)_1px,transparent_1px,transparent_8px)]" />
              <div className="bg-background relative aspect-[76/59] w-full rounded-2xl sm:w-[calc(75%+3rem)]">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeItem}
                    initial={{ opacity: 0, y: 6, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.98 }}
                    transition={{ duration: 0.2 }}
                    className="size-full overflow-hidden rounded-2xl border shadow-md"
                  >
                    {items[activeItem]?.image?.src ? (
                      <Image
                        src={items[activeItem].image.src}
                        alt={items[activeItem].image.alt || items[activeItem].title}
                        fill
                        className="object-cover object-left-top"
                      />
                    ) : (
                      <div className="w-full h-full bg-muted flex items-center justify-center">
                        <span className="text-muted-foreground text-sm">
                          {items[activeItem]?.title}
                        </span>
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </ScrollAnimation>
        </div>
      </div>
    </section>
  );
}
