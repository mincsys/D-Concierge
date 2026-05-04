import { Providers } from "./providers";
import { ChatPage } from "@/pages/chat/ChatPage";

function App() {
  return (
    <Providers>
      <ChatPage />
    </Providers>
  );
}

export default App;
