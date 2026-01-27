# Frontend Setup Notes

## Missing Dependency

The `Label` component requires `@radix-ui/react-label`. Install it:

```bash
npm install @radix-ui/react-label
```

## Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Running the App

```bash
npm install
npm run dev
```

The app will:
1. Show login page if not authenticated
2. Allow signup/login
3. Show main app with history, settings, etc. when authenticated
