import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
    {
        variants: {
            variant: {
                default:
                    "border-transparent bg-slate-900 text-slate-50 hover:bg-slate-900/80",
                secondary:
                    "border-transparent bg-slate-100 text-slate-900 hover:bg-slate-100/80",
                destructive:
                    "border-transparent bg-red-500 text-slate-50 hover:bg-red-500/80",
                outline: "text-slate-950",
                // Custom sectors
                blue: "border-transparent bg-blue-100 text-blue-900 hover:bg-blue-200",
                green: "border-transparent bg-green-100 text-green-900 hover:bg-green-200",
                purple: "border-transparent bg-purple-100 text-purple-900 hover:bg-purple-200",
                orange: "border-transparent bg-orange-100 text-orange-900 hover:bg-orange-200",
                pink: "border-transparent bg-pink-100 text-pink-900 hover:bg-pink-200",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
)

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, ...props }: BadgeProps) {
    return (
        <div className={cn(badgeVariants({ variant }), className)} {...props} />
    )
}

export { Badge, badgeVariants }
