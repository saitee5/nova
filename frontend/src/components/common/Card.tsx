import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'subtle' | 'accent' | 'critical'
  hoverEffect?: boolean
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  variant = 'default',
  hoverEffect = false,
  ...props
}) => {
  let variantClasses = 'bg-white border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)]'
  if (variant === 'subtle') variantClasses = 'bg-[#F8F9FA] border-slate-200/70 shadow-xs'
  if (variant === 'accent') variantClasses = 'bg-white border-slate-200 shadow-sm'
  if (variant === 'critical') variantClasses = 'bg-red-50/40 border-red-200 shadow-xs'

  return (
    <div
      className={`rounded-[28px] border p-6 text-slate-800 transition-all duration-200 ${variantClasses} ${
        hoverEffect ? 'hover:border-slate-300 hover:shadow-[0_6px_20px_rgba(0,0,0,0.05)]' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardHeader: React.FC<{
  title: React.ReactNode
  subtitle?: React.ReactNode
  action?: React.ReactNode
  className?: string
}> = ({ title, subtitle, action, className = '' }) => (
  <div className={`flex items-start justify-between pb-4 border-b border-slate-100 mb-4 ${className}`}>
    <div>
      <h3 className="text-base font-bold text-slate-900 tracking-tight font-heading">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 font-mono mt-0.5">{subtitle}</p>}
    </div>
    {action && <div>{action}</div>}
  </div>
)
