"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqProps {
  id?: string;
  title: string;
  description: string;
  items: FaqItem[];
  className?: string;
}

export function Faq({ id, title, description, items, className }: FaqProps) {
  const [openItem, setOpenItem] = useState<string | null>(null);

  return (
    <section id={id} className={cn("py-16 md:py-24", className)}>
      <div className="mx-auto max-w-full px-4 md:max-w-3xl md:px-8">
        <ScrollAnimation>
          <div className="mx-auto max-w-2xl text-center text-balance">
            <h2 className="text-foreground mb-4 text-3xl font-semibold tracking-tight md:text-4xl">
              {title}
            </h2>
            <p className="text-muted-foreground mb-6 md:mb-12 lg:mb-16">
              {description}
            </p>
          </div>
        </ScrollAnimation>

        <ScrollAnimation delay={0.2}>
          <div className="mx-auto mt-12 max-w-full">
            <div className="bg-muted dark:bg-muted/50 w-full rounded-2xl p-1 space-y-1">
              {items.map((item, idx) => {
                const isOpen = openItem === item.question;

                return (
                  <div className="group" key={idx}>
                    <div
                      className={cn(
                        "rounded-xl px-7 py-1 transition-all",
                        isOpen && "bg-card dark:bg-muted shadow-sm"
                      )}
                    >
                      <button
                        onClick={() =>
                          setOpenItem(isOpen ? null : item.question)
                        }
                        className="flex w-full items-center justify-between py-4 text-left text-base font-medium cursor-pointer"
                      >
                        <span>{item.question}</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 flex-shrink-0 transition-transform",
                            isOpen && "rotate-180"
                          )}
                        />
                      </button>
                      <AnimatePresence>
                        {isOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <p className="pb-4 text-base text-muted-foreground">
                              {item.answer}
                            </p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    {!isOpen && idx < items.length - 1 && (
                      <hr className="mx-7 border-dashed" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </ScrollAnimation>
      </div>
    </section>
  );
}
