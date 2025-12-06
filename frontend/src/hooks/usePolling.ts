import { useEffect, useRef } from 'react'

export function usePolling(
  callback: () => void,
  interval: number,
  enabled: boolean = true
) {
  const savedCallback = useRef(callback)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return

    const tick = () => savedCallback.current()
    const id = setInterval(tick, interval)

    return () => clearInterval(id)
  }, [interval, enabled])
}
