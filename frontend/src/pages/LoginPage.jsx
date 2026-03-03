import { useState } from 'react';
import { Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="flex flex-col min-h-screen bg-primary relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-accent/5 rounded-full blur-3xl" />
      <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-purple/3 rounded-full blur-3xl" />

      {/* Top bar */}
      <header className="h-[72px] glass-strong border-b border-surface-light/50 flex items-center px-7 gap-3 relative z-10">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Eye className="w-4 h-4 text-accent" />
          </div>
          <span className="text-lg font-bold text-white tracking-tight">
            Queue<span className="text-accent">Vision</span>
          </span>
        </Link>
      </header>

      {/* Login form */}
      <main className="flex-1 flex items-center justify-center p-6 relative z-10">
        <div className="animate-scale-in glass-strong rounded-2xl p-10 w-full max-w-md space-y-7 glow-cyan">
          {/* Header */}
          <div className="text-center space-y-2">
            <div className="w-14 h-14 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center mx-auto mb-4">
              <Lock className="w-6 h-6 text-accent" />
            </div>
            <h1 className="text-2xl font-bold">Welcome Back</h1>
            <p className="text-text-muted text-sm">Sign in to access your queue monitoring dashboard</p>
          </div>

          <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
            {/* Email */}
            <div className="space-y-2">
              <label className="text-sm text-text-secondary font-medium">Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-text-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  placeholder="you@example.com"
                  className="input pl-10"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm text-text-secondary font-medium">Password</label>
                <a href="#" className="text-xs text-accent hover:text-accent/80 transition-colors">
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-text-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  className="input pl-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-white transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember me */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="remember"
                className="w-4 h-4 rounded border-surface-light bg-surface accent-accent"
              />
              <label htmlFor="remember" className="text-sm text-text-muted cursor-pointer">
                Remember me for 30 days
              </label>
            </div>

            {/* Submit */}
            <Link
              to="/dashboard"
              className="block w-full btn-primary text-center justify-center py-3"
            >
              Sign In
            </Link>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-surface-light" />
            <span className="text-text-muted text-xs">OR</span>
            <div className="flex-1 h-px bg-surface-light" />
          </div>

          <p className="text-center text-text-muted text-sm">
            Don&apos;t have an account?{' '}
            <a href="#" className="text-accent hover:text-accent/80 font-medium transition-colors">
              Request Access
            </a>
          </p>
        </div>
      </main>
    </div>
  );
}
