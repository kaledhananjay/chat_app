// webrtc-call.js

document.addEventListener("DOMContentLoaded", () => {
  const startCall = document.getElementById("startCall");
  const pickupBtn = document.getElementById("pickupBtn");
  const ringtone = document.getElementById("ringtone");
  const modalElement = document.getElementById("incomingCallModal");
  const modalEl = new bootstrap.Modal(modalElement);

  let localStream = null;
  let peerConnection = null;
  let latestOffer = null;
  let currentCallId = null;
  let callInProgress = false;

  const receiverId = 2; // replace with actual user ID
  const callerId = 1;

  document.body.addEventListener("click", () => {
  const ringtone = document.getElementById("ringtone");
  ringtone.play().then(() => {
      ringtone.pause();
      ringtone.currentTime = 0;
      console.log("🔓 Autoplay unlocked");
    }).catch(err => {
      console.warn("❌ Still blocked:", err);
    });
  }, { once: true });

  // 🔓 Unlock audio on first click
  document.body.addEventListener(
    "click",
    () => {
      ringtone.play().then(() => {
        ringtone.pause();
        ringtone.currentTime = 0;
        console.log("🔊 Autoplay unlocked");
      }).catch(() => {});
    },
    { once: true }
  );

  // 📞 Start outgoing call
  startCall.onclick = async () => {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      peerConnection = setupPeerConnection();
      localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      const response = await fetch("/api/call/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify({
          caller: callerId,
          receiver: receiverId,
          sdp_offer: JSON.stringify(offer)
        })
      });

      const data = await response.json();
      currentCallId = data.id;
      console.log("📡 Outgoing call ID:", currentCallId);
      pollForAnswer();

    } catch (err) {
      console.error("❌ Error starting call:", err);
    }
  };

  // 🔁 Poll for incoming calls every 5 sec
  setInterval(async () => {
    if (callInProgress) return;

    try {
      const res = await fetch(`/api/call/offer?for_user=${receiverId}`);
      if (res.status !== 200) return;

      const data = await res.json();
      if (!data || !data.sdp_offer || data.sdp_offer === "test-offer") return;

      currentCallId = data.id;
      latestOffer = data.sdp_offer;
      callInProgress = true;

      modalEl.show();
      ringtone.play().catch(e => console.warn("🔇 Autoplay blocked:", e));
    } catch (err) {
      console.error("❌ Polling error:", err);
    }
  }, 5000);

  // ✅ Handle pickup
  pickupBtn.onclick = async () => {
    try {
      modalEl.hide();
      ringtone.pause();
      ringtone.currentTime = 0;

      const offer = JSON.parse(latestOffer);
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      peerConnection = setupPeerConnection();
      localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

      await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);

      await fetch("/api/call/answer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify({
          id: currentCallId,
          sdp_answer: JSON.stringify(answer)
        })
      });

      console.log("✅ Call answered");

    } catch (err) {
      console.error("❌ Pickup failed:", err);
    } finally {
      callInProgress = false;
    }
  };

  // 🔁 Poll for answer if you're the caller
  function pollForAnswer() {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/call/answer?id=${currentCallId}`);
        if (res.status !== 200) return;
        const data = await res.json();
        if (!data || !data.sdp_answer) return;

        const answer = JSON.parse(data.sdp_answer);
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
        console.log("✅ Answer received. Call connected.");
        clearInterval(interval);
      } catch (err) {
        console.error("❌ Error polling for answer:", err);
      }
    }, 3000);
  }

  // 🔧 You’ll need to define this to configure ICE/STUN:
  function setupPeerConnection() {
    return new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" }
      ]
    });
  }

  // 🔐 Get CSRF token (Django-specific)
  function getCSRFToken() {
    return document.cookie
      .split("; ")
      .find(row => row.startsWith("csrftoken="))
      ?.split("=")[1];
  }
});