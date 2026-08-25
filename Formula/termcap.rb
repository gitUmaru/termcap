class Termcap < Formula
  include Language::Python::Virtualenv

  desc "Record your terminal and export to text, SVG, GIF, PNG, JPEG, or MP4"
  homepage "https://github.com/gitUmaru/termcap"
  url "https://github.com/gitUmaru/termcap/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "3673142d5a7866b53ace1f16c2af23f38cce0720dc888566a403f2b5669a178f"
  license "MIT"

  depends_on "python@3.12"

  # Build/runtime libraries required to compile the Pillow resource from source.
  depends_on "freetype"
  depends_on "jpeg-turbo"
  depends_on "libtiff"
  depends_on "little-cms2"
  depends_on "openjpeg"
  depends_on "webp"

  # ffmpeg is optional at runtime: it enables MP4/WebM output and frame
  # extraction. Text, SVG, GIF, PNG, and JPEG output work without it.

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/1c/3d/bb7fca845737cf9d7dbde16ed1843984665ff2e0a518f5db43e77ec540b9/pillow-12.3.0.tar.gz"
    sha256 "3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce"
  end

  resource "fonttools" do
    url "https://files.pythonhosted.org/packages/84/69/c97f2c18e0db87d2c7b15da1974dace76ae938f1cfa22e2727a648b7ed43/fonttools-4.63.0.tar.gz"
    sha256 "caeb583deeb5168e694b65cda8b4ee62abedfa66cf88488734466f2366b9c4e0"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "termcap", shell_output("#{bin}/termcap --version")

    # End-to-end: record a scripted session and render it to text.
    cast = testpath/"t.cast"
    system bin/"termcap", "rec", cast, "-c", "printf", "hello\\n"
    output = shell_output("#{bin}/termcap txt #{cast} -")
    assert_match "hello", output

    # Pillow and fonttools must import (raster rendering depends on them).
    system libexec/"bin/python", "-c", "import PIL, fontTools"
  end
end
