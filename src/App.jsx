import NovaOverlay from './components/NovaOverlay'
import { useNovaState } from './hooks/useNovaState'

export default function App () {
  const { state, transcript, response, amplitude } = useNovaState()

  return (
    <NovaOverlay
      state={state}
      transcript={transcript}
      response={response}
      amplitude={amplitude}
    />
  )
}
