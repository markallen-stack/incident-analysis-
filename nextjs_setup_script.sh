#!/bin/bash
# Setup Next.js frontend for Incident Analysis System

echo "🚀 Setting up Next.js frontend..."

# Create frontend directory
mkdir -p frontend
cd frontend

# Initialize Next.js with TypeScript
npx create-next-app@latest . --typescript --tailwind --app --no-src-dir --import-alias "@/*" --yes

# Install additional dependencies
echo "📦 Installing dependencies..."
npm install \
  @tanstack/react-query \
  axios \
  date-fns \
  lucide-react \
  class-variance-authority \
  clsx \
  tailwind-merge \
  recharts \
  sonner

# Install shadcn/ui components
npx shadcn-ui@latest init -y

# Install shadcn components
npx shadcn-ui@latest add button
npx shadcn-ui@latest add card
npx shadcn-ui@latest add input
npx shadcn-ui@latest add textarea
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add alert
npx shadcn-ui@latest add progress
npx shadcn-ui@latest add separator
npx shadcn-ui@latest add toast
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add skeleton

echo "✅ Frontend setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. cd frontend"
echo "2. Copy the component files from artifacts"
echo "3. npm run dev"
echo "4. Open http://localhost:3000"
