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
  useToast,
} from "@chakra-ui/react";
import { MoonIcon, SunIcon } from "@chakra-ui/icons";
import { confirmMemory, sendPrompt } from "./services/api";


type Message = {
  sender: "user" | "ai";
  content: string;
};

const App = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const toast = useToast();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const handleSend = async () => {
    if (!input.trim()) return;

    const currentInput = input;
    setInput("");

    const userMessage: Message = { sender: "user", content: currentInput };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await sendPrompt({ prompt: currentInput });
      const cleaned = response.assistant_text || response.text || "[FRIDAY gave no valid reply]";

      const aiMessage: Message = {
        sender: "ai",
        content: cleaned,
      };

      const responsePending = Array.isArray(response.memory?.pending_ids)
        ? response.memory?.pending_ids ?? []
        : [];
      setPendingIds(responsePending);
      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "ai", content: "[Error fetching response]" },
      ]);
    }

    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  };

  const handleConfirm = async (decision: "accept" | "reject") => {
    if (!pendingIds.length || confirming) return;

    setConfirming(true);
    try {
      await confirmMemory({ pending_ids: pendingIds, decision });
      setPendingIds([]);
      toast({
        title: decision === "accept" ? "Saved" : "Discarded",
        status: "success",
        duration: 2400,
        isClosable: true,
      });
    } catch (err) {
      toast({
        title: "Memory confirmation failed",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setConfirming(false);
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

      {pendingIds.length > 0 && (
        <Box
          border="2px solid"
          borderColor={colorMode === "light" ? "#000000" : "#00FFFF"}
          borderRadius="md"
          p={3}
          mb={4}
          boxShadow="0 0 10px #00FFFF66"
        >
          <HStack justify="space-between" flexWrap="wrap" gap={3}>
            <Text>
              {pendingIds.length} memories need confirmation
            </Text>
            <HStack>
              <Button
                size="sm"
                onClick={() => handleConfirm("accept")}
                isLoading={confirming}
              >
                Accept all
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleConfirm("reject")}
                isLoading={confirming}
              >
                Reject all
              </Button>
            </HStack>
          </HStack>
        </Box>
      )}

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
