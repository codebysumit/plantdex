/**
 * PlantDex Capture & In-Browser Image Preprocessing
 * - Resizes images in the browser to max 1024px before upload (saves bandwidth & server RAM)
 * - File picker + Camera capture (capture="environment")
 * - Drag and drop support
 * - Radar scan loading feedback
 */

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("photo-input");
  const cameraInput = document.getElementById("camera-input");
  const dropZone = document.getElementById("drop-zone");
  const previewContainer = document.getElementById("preview-container");
  const previewImg = document.getElementById("preview-img");
  const scanBtn = document.getElementById("scan-btn");
  const scanOverlay = document.getElementById("scan-overlay");
  const captureForm = document.getElementById("capture-form");
  const finalFileInput = document.getElementById("processed-photo");

  let selectedBlob = null;

  function handleFileSelect(file) {
    if (!file || !file.type.startsWith("image/")) {
      alert("Please select a valid botanical image file (JPEG, PNG, WebP).");
      return;
    }

    // Downscale in browser using Canvas to max 1024px on the longest edge
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const maxDim = 1024;
        let width = img.width;
        let height = img.height;

        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            selectedBlob = blob;
            previewImg.src = URL.createObjectURL(blob);
            previewContainer.style.display = "block";
            scanBtn.removeAttribute("disabled");
            if (dropZone) dropZone.style.display = "none";
          },
          "image/jpeg",
          0.85
        );
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0]);
      }
    });
  }

  if (cameraInput) {
    cameraInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0]);
      }
    });
  }

  // Drag and Drop
  if (dropZone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
      });
    });

    dropZone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });
  }

  // Form submission handling
  if (captureForm) {
    captureForm.addEventListener("submit", (e) => {
      if (!selectedBlob) {
        e.preventDefault();
        alert("Please select or capture a plant photo first.");
        return;
      }

      // Populate file into input or submit via FormData
      e.preventDefault();
      scanBtn.setAttribute("disabled", "true");
      if (scanOverlay) scanOverlay.style.display = "flex";

      const formData = new FormData(captureForm);
      formData.set("photo", selectedBlob, "capture.jpg");

      fetch(captureForm.action, {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (response.redirected) {
            window.location.href = response.url;
          } else {
            return response.text().then((html) => {
              document.open();
              document.write(html);
              document.close();
            });
          }
        })
        .catch((err) => {
          console.error("Upload error:", err);
          alert("Identification request failed. Please check your connection.");
          scanBtn.removeAttribute("disabled");
          if (scanOverlay) scanOverlay.style.display = "none";
        });
    });
  }
});
