import { cn } from '../../lib/cn'

export default function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-raised', className)} aria-hidden />
}
