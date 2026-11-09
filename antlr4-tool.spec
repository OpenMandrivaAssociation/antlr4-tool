Name:		antlr4-tool
Version:	4.13.2
Release:	1
Summary:	ANTLR 4 grammar tool
Group:		Development/Java
License:	BSD
URL:		https://www.antlr.org/
# The git tag leaves out the generated parsers and UnicodeData. This
# sources jar is the handwritten tool plus those generated sources.
# It contains no class files.
Source0:	https://repo1.maven.org/maven2/org/antlr/antlr4/%{version}/antlr4-%{version}-sources.jar
Source1:	https://raw.githubusercontent.com/antlr/antlr4/%{version}/LICENSE.txt

BuildArch:	noarch
BuildRequires:	java-current-devel
BuildRequires:	antlr4 = %{version}
BuildRequires:	antlr-runtime
BuildRequires:	stringtemplate4 >= 4.3.4
BuildRequires:	sysjar

# build-classpath belongs to javapackages-tools, which is not installed
# in this build root. These are the jars the BuildRequires above install.
%global dep_cp %{_javadir}/antlr4-runtime.jar:%{_javadir}/antlr-runtime.jar:%{_javadir}/ST4.jar

%description
ANTLR 4 reads a grammar and generates a parser. This is the tool.
The runtime is the antlr4 package. UnicodeDataTemplateController is
omitted: it only regenerates UnicodeData, and that needs ICU. The
GUI and TestRig are omitted. tomlj runs this tool while it builds.

%prep
%setup -q -c -T -n %{name}-%{version}
jar xf %{SOURCE0}
install -m 644 %{SOURCE1} LICENSE.txt
# The controller imports com.ibm.icu. UnicodeData.java is already
# generated. Nothing outside the gui package references it.
rm -rf org/antlr/v4/gui src/org/antlr/v4/unicode/UnicodeDataTemplateController.java
rm -f org/antlr/v4/unicode/UnicodeDataTemplateController.java
mkdir -p org/antlr/v4/unicode
mv src/org/antlr/v4/unicode/UnicodeData.java org/antlr/v4/unicode/UnicodeData.java
rm -rf src
find . -name '*.g' -delete

%build
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
find org -name '*.java' > sources.list
mkdir -p classes
javac --release 11 -encoding UTF-8 \
	-cp "%{dep_cp}" \
	-d classes @sources.list
find org \( -name '*.stg' -o -name '*.st' \) > resources.list
jar cf %{name}.jar -C classes .
xargs -a resources.list jar uf %{name}.jar
cat > %{name}.pom <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.antlr</groupId>
  <artifactId>antlr4</artifactId>
  <version>%{version}</version>
  <name>ANTLR 4 Tool</name>
  <description>Grammar tool for ANTLR 4. The runtime is a separate artifact.</description>
  <url>https://www.antlr.org/</url>
  <licenses>
    <license>
      <name>BSD-3-Clause</name>
      <url>https://www.antlr.org/license.html</url>
    </license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>antlr4-runtime</artifactId>
      <version>%{version}</version>
    </dependency>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>antlr-runtime</artifactId>
      <version>3.5.3</version>
    </dependency>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>ST4</artifactId>
      <version>4.3.4</version>
    </dependency>
  </dependencies>
</project>
EOF

%check
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
mkdir -p check
cat > check/Hello.g4 <<'END'
grammar Hello;
r : 'hello' ID ;
ID : [a-z]+ ;
WS : [ \t\r\n]+ -> skip ;
END
# -o keeps the grammar's directory, so run with the grammar in the
# working directory. The output is then check/out/HelloParser.java.
(
	cd check
	java -cp ../%{name}.jar:%{dep_cp} \
		org.antlr.v4.Tool -o out Hello.g4
)
test -s check/out/HelloParser.java
test -s check/out/HelloLexer.java

%install
sysjar install --buildroot %{buildroot} \
	--artifact %{name}.pom:%{name}.jar \
	--file-name %{name} \
	--filelist .mfiles
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/antlr4 <<'EOF'
#!/bin/sh
exec java -cp %{_javadir}/antlr4-tool.jar:%{dep_cp} org.antlr.v4.Tool "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/antlr4

%files -f .mfiles
%{_bindir}/antlr4
%doc LICENSE.txt
