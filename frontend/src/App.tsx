import { useState, useRef, useEffect } from "react";
import {
  Box,
  Textarea,
  IconButton,
  useColorMode,
  VStack,
  HStack,
  Text,
  Button,
} from "@chakra-ui/react";
import { MoonIcon, SunIcon } from "@chakra-ui/icons";
import { sendPrompt } from "./services/api";
import type { ModelResponse } from "./types";


type Message = {
  sender: "user" | "ai";
  content: string;
};

const App = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

const handleSend = async () => {
  if (!input.trim()) return;

  const currentInput = input; // capture now
  setInput("");               // clear immediately for UI

  const userMessage: Message = { sender: "user", content: currentInput };
  setMessages((prev) => [...prev, userMessage]);

  try {
    const response = await sendPrompt({ prompt: currentInput });
console.log("🧠 Full model output:", response);

    // 🛠️ Access nested result fields
    const cleaned = response.result?.cleaned || response.result?.raw || "[FRIDAY gave no valid reply]";
    const affectValue = response.affect ?? "";
    const showAffect = affectValue.toLowerCase() !== "unknown" && affectValue !== "";
    const affectEmojiMap: Record<string, string> = {
      happy: "😊",
      content: "🙂",
      curious: "🤔",
      anxious: "😬",
      sad: "😢",
      surprised: "😮",
    };

    const affectEmoji = showAffect ? affectEmojiMap[affectValue.toLowerCase()] || "🧠" : "";
    const affect = showAffect ? `\n\n${affectEmoji} (${affectValue.toUpperCase()})` : "";

    const aiMessage: Message = {
      sender: "ai",
      content: cleaned + affect,
    };

    setMessages((prev) => [...prev, aiMessage]);

    } catch (err) {
    setMessages((prev) => [
      ...prev,
      { sender: "ai", content: "[Error fetching response]" },
    ]);
  }

  // Optional: this blur might not be needed anymore
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }
};


  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <Box
      bg={colorMode === "light" ? "#ffffff" : "#000000"}
      color={colorMode === "light" ? "#000000" : "#00FFFF"}
      fontFamily="friday"
      letterSpacing="wide"
      minH="100vh"
      p={6}
    >
      {/* HEADER */}
      <HStack justify="center" mb={6} position="relative">
        <Text
          fontSize="6xl"
          fontWeight="bold"
          textTransform="uppercase"
          sx={{
            fontFamily: "friday",
            color: colorMode === "light" ? "#000000" : "#00FFFF",
            textShadow: "0 0 14px #00FFFF",
          }}
        >
          FRIDAY
        </Text>
        <Box position="absolute" right="0">
          <IconButton
            aria-label="Toggle color mode"
            icon={colorMode === "light" ? <MoonIcon /> : <SunIcon />}
            onClick={toggleColorMode}
          />
        </Box>
      </HStack>

      {/* CHAT HISTORY BOX */}
      <Box
        borderRadius="lg"
        border="2px solid"
        borderColor={colorMode === "light" ? "#000000" : "#00FFFF"}
        boxShadow="0 0 14px #00FFFF, 0 0 28px #00FFFF66"
        fontFamily="friday"
        letterSpacing="wide"
        fontSize="md"
        maxH="85vh"
        overflowY="auto"
        p={4}
        mb={4}
        sx={{
          animation: "fridayPulse 6s ease-in-out infinite",
          backgroundColor: colorMode === "light" ? "#ffffff" : "#000000",
        }}
      >
        <VStack align="stretch" spacing={3}>
          {messages.map((msg, idx) => (
            <Box
              key={idx}
              alignSelf={msg.sender === "user" ? "flex-end" : "flex-start"}
              bg="transparent"
              color={colorMode === "light" ? "#000000" : "#00FFFF"}
              px={4}
              py={2}
              borderRadius="md"
              whiteSpace="pre-wrap"
              fontFamily="friday"
            >
              {msg.content}
            </Box>
          ))}
          <div ref={scrollRef} />
        </VStack>
      </Box>

      {/* INPUT + SUBMIT */}
      <Box>
        <Textarea
	  value={input}
	  onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FRIDAY something..."
          resize="vertical"
          minH="60px"
          maxH="180px"
          bg={colorMode === "light" ? "#ffffff" : "#000000"}
          color={colorMode === "light" ? "#000000" : "#00FFFF"}
          border="2px solid"
          borderColor={colorMode === "light" ? "#000000" : "#00FFFF"}
          borderRadius="md"
          boxShadow="0px 0px 12px #00FFFF"
          _placeholder={{
            color: colorMode === "light" ? "#00000088" : "#00FFFF66",
          }}
          _focus={{
            borderColor: colorMode === "light" ? "#000000" : "#00FFFF",
            boxShadow: "0px 0px 14px #00FFFF",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          sx={{
            animation: "fridayPulse 6s ease-in-out infinite",
          }}
        />

        <Button
          mt={3}
          mx="auto"
          display="block"
          onClick={handleSend}
          bg="transparent"
          border="2px solid"
          borderColor={colorMode === "light" ? "#000000" : "#00FFFF"}
          borderRadius="md"
          color={colorMode === "light" ? "#000000" : "#00FFFF"}
          textShadow="0 0 12px #00FFFF"
          boxShadow="0px 0px 12px #00FFFF"
          _hover={{ bg: "#00FFFF22" }}
          sx={{
            animation: "fridayPulse 5s ease-in-out infinite",
          }}
        >
          SUBMIT
        </Button>
      </Box>
    </Box>
  );
};

export default App;

