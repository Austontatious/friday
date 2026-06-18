import { useState, useRef, useEffect } from "react";
import {
  Box,
  Textarea,
  IconButton,
  Badge,
  useColorMode,
  VStack,
  HStack,
  Text,
  Button,
  useToast,
} from "@chakra-ui/react";
import { MoonIcon, SunIcon } from "@chakra-ui/icons";
import { useNavigate } from "react-router-dom";
import type { ChatMode } from "./services/api";
import { confirmMemory, getStoredChatMode, sendPrompt, setStoredChatMode } from "./services/api";
import { isSketchMathEnabled } from "./services/sketchmath";


type Message = {
  sender: "user" | "ai";
  content: string;
};

const App = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const navigate = useNavigate();
  const toast = useToast();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [mode, setMode] = useState<ChatMode>(() => getStoredChatMode());
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const sketchMathEnabled = isSketchMathEnabled();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.documentElement.dataset.fridayTheme = colorMode;
  }, [colorMode]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const currentInput = input;
    setInput("");

    const userMessage: Message = { sender: "user", content: currentInput };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await sendPrompt({ prompt: currentInput }, mode);
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
        {
          sender: "ai",
          content:
            mode === "althing"
              ? "[Althing mode request failed. Switch to Direct Friday or verify Althing bridge availability.]"
              : "[Direct Friday request failed.]",
        },
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

  const setActiveMode = (nextMode: ChatMode) => {
    setMode(nextMode);
    setStoredChatMode(nextMode);
  };

  return (
    <Box
      bg="var(--friday-bg)"
      color="var(--friday-text)"
      fontFamily="friday"
      letterSpacing="wide"
      minH="100vh"
      p={6}
      data-friday-shell-ui-version="2026-06-13-sketchmath-theme-tokens-v1"
    >
      {/* HEADER */}
      <HStack justify="center" mb={6} position="relative" align="start">
        <Text
          fontSize="6xl"
          fontWeight="bold"
          textTransform="uppercase"
          sx={{
            fontFamily: "friday",
            color: "var(--friday-title-fill)",
            textShadow: "var(--friday-title-shadow)",
            animation: "fridayTitlePulse 6s ease-in-out infinite",
          }}
        >
          FRIDAY
        </Text>
        <Box position="absolute" left="0" top="8px">
          <VStack align="start" spacing={2}>
            <HStack spacing={2}>
              <Text fontSize="sm" opacity={0.8}>
                Mode:
              </Text>
              <Badge colorScheme="gray">Direct Friday</Badge>
            </HStack>
            <HStack spacing={2}>
              <Button
                size="xs"
                variant="outline"
                onClick={() => setActiveMode("direct_friday")}
                borderColor="var(--friday-border)"
                color="var(--friday-control-text)"
                boxShadow="var(--friday-control-shadow)"
                _hover={{ bg: "var(--friday-control-hover-bg)" }}
              >
                Direct Friday
              </Button>
            </HStack>
          </VStack>
        </Box>
        <Box position="absolute" right="0">
          <IconButton
            aria-label="Toggle color mode"
            icon={colorMode === "light" ? <MoonIcon /> : <SunIcon />}
            onClick={toggleColorMode}
          />
          {sketchMathEnabled && (
            <Button
              size="sm"
              ml={2}
              title="AI-assisted geometry workspace"
              variant="outline"
              onClick={() => navigate("/tools/sketchmath")}
              borderColor="var(--friday-border)"
              color="var(--friday-control-text)"
              boxShadow="var(--friday-control-shadow)"
              _hover={{ bg: "var(--friday-control-hover-bg)" }}
            >
              SketchMath
            </Button>
          )}
        </Box>
      </HStack>

      {/* CHAT HISTORY BOX */}
      <Box
        borderRadius="lg"
        border="2px solid"
        borderColor="var(--friday-border)"
        boxShadow="var(--friday-control-shadow)"
        fontFamily="friday"
        letterSpacing="wide"
        fontSize="md"
        maxH="85vh"
        overflowY="auto"
        p={4}
        mb={4}
        sx={{
          animation: "fridayPulse 6s ease-in-out infinite",
          backgroundColor: "var(--friday-bg)",
        }}
      >
        <VStack align="stretch" spacing={3}>
          {messages.map((msg, idx) => (
            <Box
              key={idx}
              alignSelf={msg.sender === "user" ? "flex-end" : "flex-start"}
              bg="transparent"
              color="var(--friday-control-text)"
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
          borderColor="var(--friday-border)"
          borderRadius="md"
          p={3}
          mb={4}
          boxShadow="var(--friday-control-shadow)"
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
          bg="var(--friday-bg)"
          color="var(--friday-control-text)"
          border="2px solid"
          borderColor="var(--friday-border)"
          borderRadius="md"
          boxShadow="var(--friday-control-shadow)"
          _placeholder={{
            color: "var(--friday-placeholder)",
          }}
          _focus={{
            borderColor: "var(--friday-border)",
            boxShadow: "var(--friday-focus-ring)",
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
          borderColor="var(--friday-border)"
          borderRadius="md"
          color="var(--friday-control-text)"
          textShadow="var(--friday-title-shadow)"
          boxShadow="var(--friday-control-shadow)"
          _hover={{ bg: "var(--friday-control-hover-bg)" }}
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
