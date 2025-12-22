# AutoVoyce Frontend

Next.js frontend application for AutoVoyce, providing a modern UI for interacting with the YouTube video processing and querying system.

## Prerequisites

- Node.js 18+ and npm (or yarn/pnpm)

## Setup Instructions

### 1. Install Dependencies

```bash
cd frontend
npm install
```

Or if you prefer yarn:

```bash
yarn install
```

Or with pnpm:

```bash
pnpm install
```

### 2. Environment Variables (Optional)

If the frontend requires environment variables, create a `.env.local` file in the `frontend/` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Note:** Adjust the API URL if your backend is running on a different port or host.

## Running the Application

### Development Mode

```bash
npm run dev
```

The application will be available at `http://localhost:3000`.

### Production Build

```bash
npm run build
npm start
```

### Linting

```bash
npm run lint
```

## Project Structure

```
frontend/
├── app/                    # Next.js app directory
│   ├── chat/              # Chat page
│   ├── ingestion/         # Ingestion page
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   └── globals.css        # Global styles
├── components/            # React components
│   ├── ui/               # UI component library
│   └── ...               # Other components
├── hooks/                # Custom React hooks
├── lib/                  # Utility libraries
├── public/               # Static assets
├── styles/               # Additional styles
├── package.json          # Dependencies
└── next.config.mjs       # Next.js configuration
```

## Features

- **Chat Interface**: Interactive chat for querying the knowledge base
- **Ingestion Interface**: UI for uploading and processing YouTube videos
- **Modern UI**: Built with Radix UI and Tailwind CSS
- **Responsive Design**: Works on desktop and mobile devices
- **Theme Support**: Dark/light mode support

## API Integration

The frontend communicates with the backend API running on `http://localhost:8000` by default. The backend endpoints used are:

- `POST /upload` - Upload and process YouTube videos
- `POST /query` - Query the knowledge base

## Development

### Hot Reload

The development server supports hot module replacement (HMR), so changes to your code will automatically refresh in the browser.

### TypeScript

This project uses TypeScript. Make sure to type your components and functions properly.

### Styling

- **Tailwind CSS**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **Custom Components**: Located in `components/ui/`

## Troubleshooting

- **Port already in use**: Change the port by running `npm run dev -- -p 3001`
- **Build errors**: Make sure all dependencies are installed with `npm install`
- **API connection errors**: Verify the backend is running on `http://localhost:8000`
- **TypeScript errors**: Run `npm run lint` to check for type errors

## Deployment

### Vercel (Recommended)

The easiest way to deploy Next.js is using [Vercel](https://vercel.com):

1. Push your code to GitHub
2. Import your repository in Vercel
3. Configure environment variables
4. Deploy

### Other Platforms

Next.js can be deployed to any platform that supports Node.js:
- AWS Amplify
- Netlify
- Railway
- Docker containers

## License

[Add your license here]

