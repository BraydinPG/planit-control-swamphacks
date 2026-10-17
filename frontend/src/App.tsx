import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <section className="flex grow flex-col items-center justify-center gap-6 px-5 py-8">
        <div className="relative">
          <img
            src={heroImg}
            className="relative z-0 w-[170px]"
            width="170"
            height="179"
            alt=""
          />
          <img
            src={reactLogo}
            className="absolute inset-x-0 top-[34px] z-10 mx-auto h-7 [transform:perspective(2000px)_rotateZ(300deg)_rotateX(44deg)_rotateY(39deg)_scale(1.4)]"
            alt="React logo"
          />
          <img
            src={viteLogo}
            className="absolute inset-x-0 top-[107px] z-0 mx-auto h-[26px] w-auto [transform:perspective(2000px)_rotateZ(300deg)_rotateX(40deg)_rotateY(39deg)_scale(0.8)]"
            alt="Vite logo"
          />
        </div>
        <div>
          <h1 className="my-8 text-4xl font-medium tracking-tight text-neutral-950 sm:text-5xl dark:text-neutral-100">
            Get started
          </h1>
          <p>
            Edit <code className="rounded bg-neutral-100 px-2 py-1 font-mono text-[15px] text-neutral-950 dark:bg-neutral-800 dark:text-neutral-100">src/App.tsx</code> and save to test{' '}
            <code className="rounded bg-neutral-100 px-2 py-1 font-mono text-[15px] text-neutral-950 dark:bg-neutral-800 dark:text-neutral-100">HMR</code>
          </p>
        </div>
        <button
          type="button"
          className="mb-6 rounded-md border-2 border-transparent bg-violet-500/10 px-2.5 py-1 font-mono text-base text-violet-600 hover:border-violet-500/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 dark:text-violet-300"
          onClick={() => setCount((count) => count + 1)}
        >
          Count is {count}
        </button>
      </section>

      <div className="relative before:absolute before:-top-1 before:left-0 before:border-[5px] before:border-transparent before:border-l-neutral-200 after:absolute after:-top-1 after:right-0 after:border-[5px] after:border-transparent after:border-r-neutral-200 dark:before:border-l-neutral-800 dark:after:border-r-neutral-800" />

      <section className="flex flex-col border-t border-neutral-200 text-left md:flex-row dark:border-neutral-800">
        <div className="flex-1 border-b border-neutral-200 px-5 py-6 md:border-r md:border-b-0 md:px-8 md:py-8 dark:border-neutral-800">
          <svg className="mb-4 size-[22px]" role="presentation" aria-hidden="true">
            <use href="/icons.svg#documentation-icon"></use>
          </svg>
          <h2 className="mb-2 text-xl font-medium text-neutral-950 md:text-2xl dark:text-neutral-100">
            Documentation
          </h2>
          <p>Your questions, answered</p>
          <ul className="mt-5 flex list-none flex-wrap justify-center gap-2 p-0 md:mt-8 md:justify-start">
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://vite.dev/"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <img className="h-[18px]" src={viteLogo} alt="" />
                Explore Vite
              </a>
            </li>
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://react.dev/"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <img className="size-[18px]" src={reactLogo} alt="" />
                Learn more
              </a>
            </li>
          </ul>
        </div>
        <div className="flex-1 px-5 py-6 md:px-8 md:py-8">
          <svg className="mb-4 size-[22px] dark:invert dark:brightness-200" role="presentation" aria-hidden="true">
            <use href="/icons.svg#social-icon"></use>
          </svg>
          <h2 className="mb-2 text-xl font-medium text-neutral-950 md:text-2xl dark:text-neutral-100">
            Connect with us
          </h2>
          <p>Join the Vite community</p>
          <ul className="mt-5 flex list-none flex-wrap justify-center gap-2 p-0 md:mt-8 md:justify-start">
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://github.com/vitejs/vite"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <svg className="size-[18px] dark:invert dark:brightness-200" role="presentation" aria-hidden="true">
                  <use href="/icons.svg#github-icon"></use>
                </svg>
                GitHub
              </a>
            </li>
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://chat.vite.dev/"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <svg className="size-[18px] dark:invert dark:brightness-200" role="presentation" aria-hidden="true">
                  <use href="/icons.svg#discord-icon"></use>
                </svg>
                Discord
              </a>
            </li>
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://x.com/vite_js"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <svg className="size-[18px] dark:invert dark:brightness-200" role="presentation" aria-hidden="true">
                  <use href="/icons.svg#x-icon"></use>
                </svg>
                X.com
              </a>
            </li>
            <li className="min-w-[calc(50%-0.5rem)] flex-1 md:min-w-0 md:flex-none">
              <a
                href="https://bsky.app/profile/vite.dev"
                target="_blank"
                className="flex items-center justify-center gap-2 rounded-md bg-neutral-100 px-3 py-1.5 text-base text-neutral-950 no-underline hover:shadow-md md:justify-start dark:bg-neutral-800 dark:text-neutral-100"
              >
                <svg className="size-[18px] dark:invert dark:brightness-200" role="presentation" aria-hidden="true">
                  <use href="/icons.svg#bluesky-icon"></use>
                </svg>
                Bluesky
              </a>
            </li>
          </ul>
        </div>
      </section>

      <div className="relative before:absolute before:-top-1 before:left-0 before:border-[5px] before:border-transparent before:border-l-neutral-200 after:absolute after:-top-1 after:right-0 after:border-[5px] after:border-transparent after:border-r-neutral-200 dark:before:border-l-neutral-800 dark:after:border-r-neutral-800" />
      <section className="h-12 border-t border-neutral-200 md:h-[88px] dark:border-neutral-800" />
    </>
  )
}

export default App
