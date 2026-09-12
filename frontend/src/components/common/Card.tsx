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
  let variantClasses = 'bg-white border-slate-200 shadow-sm'
  if (variant === 'subtle') variantClasses = 'bg-slate-50 border-slate-200'
  if (variant === 'accent') variantClasses = 'bg-orange-50/50 border-orange-200'
  if (variant === 'critical') variantClasses = 'bg-red-50/50 border-red-200'

  return (
    <div
      className={`rounded-lg border p-4 text-slate-800 transition-all duration-200 ${variantClasses} ${
        hoverEffect ? 'hover:shadow-md hover:border-slate-300' : ''
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
  <div className={`flex items-start justify-between pb-3 border-b border-slate-100 mb-3 ${className}`}>
    <div>
      <h3 className="text-sm font-semibold text-slate-900 tracking-tight">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 font-mono mt-0.5">{subtitle}</p>}
    </div>
    {action && <div>{action}</div>}
  </div>
)
