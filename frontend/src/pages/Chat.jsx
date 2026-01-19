import React, { useState, useEffect, useRef } from 'react';
import { chatAPI, productsAPI } from '../services/api';
import { Send, Loader, MessageCircle, Sparkles } from 'lucide-react';

const Chat = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random()}`);
  const [suggestions, setSuggestions] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadProducts();
    loadSuggestions();
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
    setLoading(true);

    try {
      const response = await chatAPI.ask({
        product_id: selectedProduct || null,
        session_id: sessionId,
        question: currentQuestion,
        language: 'auto'
      });

      const assistantMessage = {
        role: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        responseTime: response.data.response_time,
        cached: response.data.cached,
        detectedLanguage: response.data.detected_language,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
        error: true,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <MessageCircle className="w-8 h-8 text-indigo-600" />
              <h1 className="text-2xl font-bold text-gray-800">Insurance FAQ Chatbot</h1>
            </div>
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-gray-700">Product:</label>
              <select
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
              <Sparkles className="w-16 h-16 text-indigo-300 mx-auto mb-4" />
              <h2 className="text-2xl font-semibold text-gray-700 mb-2">
                Welcome to Insurance FAQ
              </h2>
              <p className="text-gray-500 mb-6">
                Ask me anything about insurance policies, coverage, claims, and more.
              </p>

              {suggestions.length > 0 && (
                <div className="mt-8">
                  <p className="text-sm font-medium text-gray-600 mb-3">Suggested questions:</p>
                  <div className="space-y-2">
                    {suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={(e) => handleSubmit(e, suggestion)}
                        className="block w-full max-w-2xl mx-auto px-4 py-3 bg-white border border-gray-200 rounded-lg hover:border-indigo-300 hover:shadow-md transition-all text-left text-sm text-gray-700"
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
              className={`mb-4 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-3xl px-6 py-4 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : message.error
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-white shadow-md border border-gray-200'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>

                {message.role === 'assistant' && !message.error && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                      {message.cached && (
                        <span className="bg-green-100 text-green-700 px-2 py-1 rounded">
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

          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-white shadow-md border border-gray-200 px-6 py-4 rounded-lg">
                <Loader className="w-5 h-5 animate-spin text-indigo-600" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="bg-white border-t shadow-lg">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about insurance..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition duration-200 disabled:bg-gray-400 flex items-center gap-2"
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
