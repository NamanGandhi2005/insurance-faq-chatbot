import React, { useState, useEffect, useRef } from 'react';
import { chatAPI, productsAPI } from '../services/api';
import { Send, Loader, MessageCircle, Sparkles } from 'lucide-react';

const Chat = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random()}`);
  const [suggestions, setSuggestions] = useState([]);
  const messagesEndRef = useRef(null);
  const lastMessageRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    loadProducts();
    loadSuggestions();
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list();
      setProducts(response.data);
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const loadSuggestions = async () => {
    try {
      const response = await chatAPI.getSuggestions();
      setSuggestions(response.data.questions.slice(0, 5));
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    }
  };

  const handleSubmit = async (e, suggestedQuestion = null) => {
    if (e) e.preventDefault();

    const currentQuestion = suggestedQuestion || question;
    if (!currentQuestion.trim()) return;

    const userMessage = {
      role: 'user',
      content: currentQuestion,
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setQuestion('');

    const assistantMessage = { role: 'assistant', content: '', sources: [], timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, assistantMessage]);

    lastMessageRef.current = assistantMessage;
    
    const updateMessage = () => {
        setMessages(prev => {
            const newMessages = [...prev];
            const lastMsgIndex = newMessages.length - 1;
            if (newMessages[lastMsgIndex].role === 'assistant') {
                newMessages[lastMsgIndex] = lastMessageRef.current;
            }
            return newMessages;
        });
        animationFrameRef.current = null;
    };
    
    try {
      await chatAPI.askStream({
        product_id: selectedProduct || null,
        session_id: sessionId,
        question: currentQuestion,
        language: 'auto'
      }, (chunk) => {
        if (chunk.type === 'token') {
          lastMessageRef.current.content += chunk.content;
        } else if (chunk.type === 'meta') {
          lastMessageRef.current.sources = chunk.sources;
          lastMessageRef.current.debug_info = chunk.debug;
        } else if (chunk.type === 'error') {
          lastMessageRef.current.error = true;
          lastMessageRef.current.content = chunk.content;
        }
        
        if (!animationFrameRef.current) {
          animationFrameRef.current = requestAnimationFrame(updateMessage);
        }
      });
    } catch (error) {
        lastMessageRef.current.error = true;
        lastMessageRef.current.content = 'Sorry, I encountered an error processing your question. Please try again.';
        if (!animationFrameRef.current) {
          animationFrameRef.current = requestAnimationFrame(updateMessage);
        }
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white shadow-sm border-b dark:bg-gray-800 dark:border-gray-700">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <MessageCircle className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
              <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200">Insurance FAQ Chatbot</h1>
            </div>
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Product:</label>
              <select
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
              >
                <option value="">All Products</option>
                {products.map(product => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="mx-auto bg-indigo-100 dark:bg-indigo-900 rounded-full p-4 w-24 h-24 flex items-center justify-center">
                <MessageCircle className="w-16 h-16 text-indigo-500 dark:text-indigo-400" />
              </div>
              <h2 className="mt-6 text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Insurance FAQ Chatbot
              </h2>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                Your AI assistant for policy questions.
              </p>

              {suggestions.length > 0 && (
                <div className="mt-8">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">Suggested questions:</p>
                  <div className="space-y-2">
                    {suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={(e) => handleSubmit(e, suggestion)}
                        className="block w-full max-w-2xl mx-auto px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-indigo-300 dark:hover:border-indigo-500 hover:shadow-md transition-all text-left text-sm text-gray-700 dark:text-gray-300"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`mb-4 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} message-appear`}
            >
              <div
                className={`max-w-3xl px-6 py-4 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : message.error
                    ? 'bg-red-50 text-red-700 border border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800'
                    : 'bg-white dark:bg-gray-800 shadow-md border border-gray-200 dark:border-gray-700'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>

                {message.role === 'assistant' && !message.error && (
                  <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                    <div className="flex flex-wrap gap-3 text-xs text-gray-500 dark:text-gray-400">
                      {message.cached && (
                        <span className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 px-2 py-1 rounded">
                          Cached
                        </span>
                      )}
                      <span>Response time: {message.responseTime?.toFixed(2)}s</span>
                      <span>Language: {message.detectedLanguage}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 border-t dark:border-gray-700 shadow-lg">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about insurance..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
            />
            <button
              type="submit"
              disabled={!question.trim()}
              className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition duration-200 disabled:bg-gray-400 dark:disabled:bg-gray-500 flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Chat;
