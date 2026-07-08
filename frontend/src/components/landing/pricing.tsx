"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Zap, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

const iconMap: Record<string, LucideIcon> = {
  Zap,
};

interface PricingItem {
  product_id: string;
  title: string;
  description: string;
  price: string;
  unit?: string;
  original_price?: string;
  features: string[];
  button: {
    title: string;
    url: string;
    icon?: string;
  };
  is_featured?: boolean;
  label?: string;
  group: string;
}

interface PricingGroup {
  name: string;
  title: string;
  label?: string;
  is_featured?: boolean;
}

interface PricingProps {
  id?: string;
  title: string;
  description: string;
  groups?: PricingGroup[];
  items: PricingItem[];
  className?: string;
}

export function Pricing({
  id,
  title,
  description,
  groups,
  items,
  className,
}: PricingProps) {
  const [group, setGroup] = useState(() => {
    const featuredGroup = groups?.find((g) => g.is_featured);
    return featuredGroup?.name || groups?.[0]?.name || "monthly";
  });

  const filteredItems = items.filter((item) => !item.group || item.group === group);

  return (
    <section id={id} className={cn("py-24 md:py-36", className)}>
      <div className="mx-auto mb-12 px-4 text-center md:px-8">
        <h2 className="mb-6 text-3xl font-bold text-pretty lg:text-4xl">
          {title}
        </h2>
        <p className="text-muted-foreground mx-auto mb-4 max-w-xl lg:max-w-none lg:text-lg">
          {description}
        </p>
      </div>

      <div className="container">
        {groups && groups.length > 0 && (
          <div className="mx-auto mt-8 mb-16 flex w-full justify-center md:max-w-lg">
            <Tabs value={group} onValueChange={setGroup}>
              <TabsList>
                {groups.map((item, i) => (
                  <TabsTrigger key={i} value={item.name}>
                    {item.title}
                    {item.label && (
                      <Badge className="ml-2" variant="secondary">
                        {item.label}
                      </Badge>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        )}

        <div
          className={cn(
            "mx-auto mt-0 grid w-full gap-6",
            filteredItems.length === 1 && "max-w-sm",
            filteredItems.length === 2 && "max-w-2xl md:grid-cols-2",
            filteredItems.length >= 3 && "max-w-5xl md:grid-cols-3"
          )}
        >
          {filteredItems.map((item, idx) => (
            <Card key={idx} className="relative">
              {item.label && (
                <span className="absolute inset-x-0 -top-3 mx-auto flex h-6 w-fit items-center rounded-full bg-gradient-to-br from-purple-400 to-amber-300 px-3 py-1 text-xs font-medium text-amber-950">
                  {item.label}
                </span>
              )}

              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  {item.title}
                </CardTitle>

                <div className="my-3 flex items-baseline gap-2">
                  {item.original_price && (
                    <span className="text-muted-foreground text-sm line-through">
                      {item.original_price}
                    </span>
                  )}

                  <div className="my-3 block text-2xl font-semibold">
                    <span className="text-primary">{item.price}</span>{" "}
                    {item.unit && (
                      <span className="text-muted-foreground text-sm font-normal">
                        {item.unit}
                      </span>
                    )}
                  </div>
                </div>

                <CardDescription className="text-sm">
                  {item.description}
                </CardDescription>

                <Button asChild className="mt-4 h-9 w-full px-4 py-2">
                  <Link href={item.button.url}>
                    {item.button.icon && iconMap[item.button.icon] && (
                      (() => {
                        const Icon = iconMap[item.button.icon];
                        return <Icon className="mr-2 h-4 w-4" />;
                      })()
                    )}
                    <span>{item.button.title}</span>
                  </Link>
                </Button>
              </CardHeader>

              <CardContent className="space-y-4">
                <hr className="border-dashed" />

                <ul className="list-outside space-y-3 text-sm">
                  {item.features?.map((feature, index) => (
                    <li key={index} className="flex items-center gap-2">
                      <Check className="size-3 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
