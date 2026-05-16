# DrawIO Diagram Creation Guide for AI Agents

> A comprehensive guide to generating UML diagrams in DrawIO XML format programmatically.
> This document covers structure, styling, common patterns, and best practices for creating professional technical diagrams.

---

## Table of Contents

1. [DrawIO XML Structure](#drawio-xml-structure)
2. [Core Components](#core-components)
3. [Styling System](#styling-system)
4. [Diagram Types](#diagram-types)
5. [Common Patterns](#common-patterns)
6. [Best Practices](#best-practices)
7. [Examples](#examples)

---

## DrawIO XML Structure

### Basic Template

Every DrawIO diagram is an XML file with this minimal structure:

```xml

  
    
    
  

```

### Attribute Explanation

| Attribute | Default | Purpose |
|-----------|---------|---------|
| `dx`, `dy` | 947, 917 | Canvas dimensions |
| `gridSize` | 10 | Grid unit size for snapping |
| `guides` | 1 | Show alignment guides |
| `tooltips` | 1 | Enable hover tooltips |
| `arrows` | 1 | Enable arrow rendering |
| `pageWidth` | 827 | Standard A4 width (in pixels) |
| `pageHeight` | 1169 | Standard A4 height (in pixels) |
| `shadow` | 0 | Disable drop shadows for cleaner output |

### Root Cells

```xml

             
   
  

```

---

## Core Components

### 1. Basic Shape (mxCell)

Every visual element is an `<mxCell>` with:
- `id` — unique identifier (string or UUID)
- `value` — text label/content
- `style` — CSS-like style string
- `parent` — parent cell ID (usually "1" for canvas)
- `vertex` — "1" if it's a shape, omit if edge/arrow
- `edge` — "1" if it's a connection/arrow, omit if shape
- `<mxGeometry>` — position and size

#### Example Shape
```xml

  

```

### 2. Geometry (mxGeometry)

Defines position and size:
```xml

```

- `x`, `y` — top-left position on canvas
- `width`, `height` — dimensions in pixels
- Child `<Array>` element — waypoints/routing points for arrows

#### Example with Routing Points
```xml

  
    
    
  

```

### 3. Connections (Edges/Arrows)

```xml

  

```

- `source` — source cell ID
- `target` — target cell ID
- `edge="1"` — marks as connection
- `value` — label text
- Arrow styling controls how it connects

---

## Styling System

### Style String Format

Styles are semicolon-separated key=value pairs:

```
shape=component;fillColor=#e1d5e7;strokeColor=#9673a6;fontColor=#333333;html=1;
```

### Common Shape Types

| Shape | Style Value | Use Case |
|-------|-------------|----------|
| Rectangle | `rounded=0;` or omitted | Generic box |
| Rounded Rectangle | `rounded=1;arcSize=50;` | Process/action box |
| Diamond | `shape=rhombus;` | Decision/condition |
| Ellipse/Circle | `shape=ellipse;` or `shape=doubleEllipse;` | Start/end node |
| Component Box | `shape=component;` | Software/system component |
| UML Lifeline | `shape=umlLifeline;` | Sequence diagram actor |
| UML Frame | `shape=umlFrame;` | Fragment/loop container |

### Color Palette (Recommended)

Use consistent colors for visual hierarchy:

```
Perception/Process:  #e1d5e7 (light purple)   stroke: #9673a6
Analytics/Data:      #d5e8d4 (light green)    stroke: #82b366
I/O/External:        #f5f5f5 (light gray)     stroke: #666666
Config/Optional:     #ffe6cc (light orange)   stroke: #d79b00
Error/Exception:     #f8cecc (light red)      stroke: #b85450
Decision/Branch:     #fff2cc (light yellow)   stroke: #d6b656
```

### Common Style Combinations

#### Perception Component
```
shape=component;align=left;spacingLeft=36;html=1;
fillColor=#e1d5e7;strokeColor=#9673a6;whiteSpace=wrap;
```

#### Action/Process Box
```
rounded=1;whiteSpace=wrap;html=1;arcSize=50;
fillColor=#d5e8d4;strokeColor=#82b366;
```

#### Decision Diamond
```
rhombus;whiteSpace=wrap;html=1;
fillColor=#fff2cc;strokeColor=#d6b656;verticalAlign=middle;
```

#### UML Lifeline (Sequence Diagram)
```
shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;
container=0;dropTarget=0;collapsible=0;recursiveResize=0;
outlineConnect=0;portConstraint=eastwest;fillColor=#e1d5e7;strokeColor=#9673a6;
```

### Arrow Styles

#### Solid Arrow (Method Call)
```
html=1;verticalAlign=bottom;startArrow=oval;endArrow=block;startSize=8;
edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;
```

#### Dashed Arrow (Return/Optional)
```
html=1;verticalAlign=bottom;endArrow=open;dashed=1;endSize=8;
edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;
```

#### Block Arrow (Simple Flow)
```
html=1;verticalAlign=bottom;endArrow=block;endFill=1;rounded=0;
```

### Font Styling

| Style | Purpose |
|-------|---------|
| `fontSize=14;fontStyle=1;` | Large bold title |
| `fontSize=11;fontStyle=2;` | Medium bold label |
| `fontSize=10;fontColor=#666666;` | Small gray subtext |
| `align=center;verticalAlign=middle;` | Center text in box |

---

## Diagram Types

### 1. Component Diagram

**Purpose:** Show system architecture and module relationships

**Key Elements:**
- Components: `shape=component`
- Connections: solid arrows for dependencies
- Dashed arrows for configuration/optional flows
- System boundary: `shape=umlFrame;dashed=1;`

**Template:**
```xml



  



  



  



  



  

```

### 2. Activity Diagram

**Purpose:** Show process flow and control logic

**Key Elements:**
- Start: `shape=doubleEllipse;` (filled black circle)
- End: `shape=doubleEllipse;` (filled black circle)
- Activity: `rounded=1;arcSize=50;`
- Decision: `shape=rhombus;`
- Arrows between all elements

**Template:**
```xml
<mxfile host="65bd71144e" pages="2">
    <diagram id="dY45TQ-w7fdcfm2Qn3ZN" name="Example">
        <mxGraphModel dx="415" dy="598" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1019" pageHeight="1320" math="0" shadow="0">
            <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-1" value="Actors" style="swimlane;html=1;childLayout=stackLayout;resizeParent=1;resizeParentMax=0;horizontal=0;startSize=20;horizontalStack=0;whiteSpace=wrap;verticalAlign=middle;" parent="1" vertex="1">
                    <mxGeometry x="30" y="20" width="890" height="510" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-2" value="&lt;div&gt;Orders&lt;/div&gt;" style="swimlane;html=1;startSize=20;horizontal=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-1" vertex="1">
                    <mxGeometry x="20" width="870" height="270" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-3" value="" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=20;dashed=1;fontColor=#333333;fillColor=#f9f9f9;strokeColor=#999999;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="90" y="10" width="480" height="170" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-4" value="&lt;div&gt;Receive &lt;br&gt;&lt;/div&gt;&lt;div&gt;order&lt;/div&gt;" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="104" y="105" width="66" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-5" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-6" target="bPOVIzieLG1AcJA_SuyZ-17" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <Array as="points">
                            <mxPoint x="215" y="75"/>
                            <mxPoint x="770" y="75"/>
                        </Array>
                        <mxPoint x="675" y="110" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-6" value="" style="rhombus;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="200" y="110" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-7" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-4" target="bPOVIzieLG1AcJA_SuyZ-6" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-8" value="Fill order" style="html=1;align=center;verticalAlign=middle;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="320" y="105" width="60" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-9" value="[order accepted]" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;labelBackgroundColor=none;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-6" target="bPOVIzieLG1AcJA_SuyZ-8" edge="1">
                    <mxGeometry x="-0.1111" y="-10" relative="1" as="geometry">
                        <mxPoint as="offset"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-10" value="" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#000000;strokeColor=none;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="410" y="85" width="5" height="80" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-11" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-8" target="bPOVIzieLG1AcJA_SuyZ-10" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-12" value="Prepare &lt;br&gt;shipment" style="html=1;align=center;verticalAlign=middle;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="470" y="105" width="80" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-13" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-10" target="bPOVIzieLG1AcJA_SuyZ-12" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <Array as="points"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-14" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;labelBackgroundColor=none;endArrow=classic;endFill=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-15" target="bPOVIzieLG1AcJA_SuyZ-25" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-15" value="" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#000000;strokeColor=none;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="610" y="85" width="5" height="80" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-16" value="" style="edgeStyle=none;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-12" target="bPOVIzieLG1AcJA_SuyZ-15" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-17" value="&lt;div&gt;Close &lt;br&gt;&lt;/div&gt;&lt;div&gt;order&lt;/div&gt;" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="745" y="105" width="60" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-18" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-25" target="bPOVIzieLG1AcJA_SuyZ-17" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <mxPoint x="690" y="125" as="sourcePoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-19" value="" style="ellipse;html=1;shape=endState;fillColor=#000000;strokeColor=#000000;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="830" y="210" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-20" value="" style="rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-17" target="bPOVIzieLG1AcJA_SuyZ-19" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-21" value="Order cancel request" style="html=1;shape=mxgraph.infographic.ribbonSimple;notch1=20;notch2=0;align=center;verticalAlign=middle;fontSize=14;fontStyle=0;fillColor=#f8cecc;flipH=0;spacingRight=0;spacingLeft=14;strokeColor=#b85450;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="380" y="20" width="170" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-22" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-23" target="bPOVIzieLG1AcJA_SuyZ-19" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-23" value="&lt;div&gt;Cancel &lt;br&gt;&lt;/div&gt;&lt;div&gt;order&lt;/div&gt;" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#f8cecc;strokeColor=#b85450;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="745" y="20" width="60" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-24" value="" style="shape=mxgraph.lean_mapping.electronic_info_flow_edge;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-2" source="bPOVIzieLG1AcJA_SuyZ-21" target="bPOVIzieLG1AcJA_SuyZ-23" edge="1">
                    <mxGeometry width="160" relative="1" as="geometry">
                        <mxPoint x="640" y="-60" as="sourcePoint"/>
                        <mxPoint x="800" y="-60" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-25" value="&lt;div&gt;Ship&lt;br&gt;&lt;/div&gt;&lt;div&gt;order&lt;/div&gt;" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#fff2cc;strokeColor=#d6b656;" parent="bPOVIzieLG1AcJA_SuyZ-2" vertex="1">
                    <mxGeometry x="650" y="105" width="60" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-26" value="Accounting" style="swimlane;html=1;startSize=20;horizontal=0;fillColor=#d5e8d4;strokeColor=#82b366;" parent="bPOVIzieLG1AcJA_SuyZ-1" vertex="1">
                    <mxGeometry x="20" y="270" width="870" height="120" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-27" value="Send invoice" style="html=1;align=center;verticalAlign=middle;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#d5e8d4;strokeColor=#82b366;" parent="bPOVIzieLG1AcJA_SuyZ-26" vertex="1">
                    <mxGeometry x="240" y="40" width="90" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-28" value="&lt;div&gt;Accept &lt;br&gt;&lt;/div&gt;&lt;div&gt;payment&lt;/div&gt;" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#d5e8d4;strokeColor=#82b366;" parent="bPOVIzieLG1AcJA_SuyZ-26" vertex="1">
                    <mxGeometry x="540" y="30" width="70" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-29" value="Customer" style="swimlane;html=1;startSize=20;horizontal=0;fillColor=#e1d5e7;strokeColor=#9673a6;" parent="bPOVIzieLG1AcJA_SuyZ-1" vertex="1">
                    <mxGeometry x="20" y="390" width="870" height="120" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-30" value="&lt;div&gt;Send &lt;br&gt;&lt;/div&gt;&lt;div&gt;payment&lt;/div&gt;" style="html=1;align=center;verticalAlign=middle;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fillColor=#e1d5e7;strokeColor=#9673a6;" parent="bPOVIzieLG1AcJA_SuyZ-29" vertex="1">
                    <mxGeometry x="470" y="40" width="70" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-33" value="" style="ellipse;fillColor=#000000;strokeColor=none;" parent="bPOVIzieLG1AcJA_SuyZ-29" vertex="1">
                    <mxGeometry x="30" y="45" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-34" value="Submit order" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;" parent="bPOVIzieLG1AcJA_SuyZ-29" vertex="1">
                    <mxGeometry x="102" y="40" width="70" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-35" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-29" source="bPOVIzieLG1AcJA_SuyZ-33" target="bPOVIzieLG1AcJA_SuyZ-34" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-36" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.2;exitY=0.613;exitDx=0;exitDy=0;exitPerimeter=0;" parent="bPOVIzieLG1AcJA_SuyZ-1" source="bPOVIzieLG1AcJA_SuyZ-10" target="bPOVIzieLG1AcJA_SuyZ-27" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <mxPoint x="585" y="60" as="sourcePoint"/>
                        <Array as="points">
                            <mxPoint x="431" y="140"/>
                            <mxPoint x="470" y="140"/>
                            <mxPoint x="470" y="200"/>
                            <mxPoint x="305" y="200"/>
                        </Array>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-37" style="edgeStyle=none;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-1" source="bPOVIzieLG1AcJA_SuyZ-30" target="bPOVIzieLG1AcJA_SuyZ-28" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-38" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="bPOVIzieLG1AcJA_SuyZ-1" source="bPOVIzieLG1AcJA_SuyZ-28" target="bPOVIzieLG1AcJA_SuyZ-15" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <Array as="points">
                            <mxPoint x="600" y="150"/>
                        </Array>
                    </mxGeometry>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-40" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;endFill=1;" parent="bPOVIzieLG1AcJA_SuyZ-1" source="bPOVIzieLG1AcJA_SuyZ-34" target="bPOVIzieLG1AcJA_SuyZ-4" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-31" value="Invoice" style="text;align=center;verticalAlign=middle;dashed=0;fillColor=#ffffff;strokeColor=#000000;" parent="1" vertex="1">
                    <mxGeometry x="414" y="391" width="60" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-39" style="rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="1" source="bPOVIzieLG1AcJA_SuyZ-27" target="bPOVIzieLG1AcJA_SuyZ-31" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
                <mxCell id="bPOVIzieLG1AcJA_SuyZ-32" style="edgeStyle=none;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" parent="1" source="bPOVIzieLG1AcJA_SuyZ-31" target="bPOVIzieLG1AcJA_SuyZ-30" edge="1">
                    <mxGeometry relative="1" as="geometry"/>
                </mxCell>
            </root>
        </mxGraphModel>
    </diagram>
    <diagram id="KGbCpBdcf_usR9CPnqUh" name="Activity diagram shapes">
        <mxGraphModel dx="415" dy="598" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0">
            <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-1" value="Action" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=10;dashed=0;fontSize=11;spacingTop=8;" parent="1" vertex="1">
                    <mxGeometry x="127.5" y="80" width="105" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-3" value="&lt;div style=&quot;font-size: 11px;&quot;&gt;Join or &lt;br style=&quot;font-size: 11px;&quot;&gt;synchronise&lt;/div&gt;" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=strokeColor;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingRight=0;spacingLeft=6;spacingTop=-35;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="447.5" y="160" width="5" height="80" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-5" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-3" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="417.5" y="180" as="sourcePoint"/>
                        <mxPoint x="757.5" y="280" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-6" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-3" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="417.5" y="220" as="sourcePoint"/>
                        <mxPoint x="757.5" y="280" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-8" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" source="k5bAv-KiF9-cGLeYmeqg-3" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="707.5" y="330" as="sourcePoint"/>
                        <mxPoint x="507.5" y="200" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-9" value="Fork" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=strokeColor;labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingTop=-18;spacingRight=8;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="327.5" y="160" width="5" height="80" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-10" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-9" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="287.5" y="200" as="sourcePoint"/>
                        <mxPoint x="437.5" y="280" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-11" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" source="k5bAv-KiF9-cGLeYmeqg-9" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="330.5" y="170" as="sourcePoint"/>
                        <mxPoint x="377.5" y="180" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-12" value="" style="endArrow=classic;html=1;rounded=0;fontSize=11;" parent="1" source="k5bAv-KiF9-cGLeYmeqg-9" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="342.5" y="180" as="sourcePoint"/>
                        <mxPoint x="377.5" y="220" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-13" value="" style="endArrow=classic;html=1;rounded=0;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;strokeWidth=1;fontSize=11;" parent="1" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="127.5" y="180" as="sourcePoint"/>
                        <mxPoint x="247.5" y="180" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-14" value="Control flow (or object flow)" style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=11;" parent="k5bAv-KiF9-cGLeYmeqg-13" vertex="1" connectable="0">
                    <mxGeometry x="-0.65" y="1" relative="1" as="geometry">
                        <mxPoint x="29" y="-9" as="offset"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-15" value="Decision" style="rhombus;whiteSpace=wrap;html=1;labelPosition=center;verticalLabelPosition=middle;align=center;verticalAlign=middle;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="147.5" y="270" width="65" height="60" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-16" value="Object" style="html=1;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="350" y="80" width="90" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-18" value="Note" style="shape=note2;boundedLbl=1;whiteSpace=wrap;html=1;size=15;verticalAlign=middle;align=center;labelPosition=center;verticalLabelPosition=middle;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="572.5" y="80" width="80" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-19" value="Interruptible activity region" style="html=1;align=center;verticalAlign=top;rounded=1;absoluteArcSize=1;arcSize=20;dashed=1;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="720" y="67.5" width="160" height="65" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-20" value="Interrupt flow" style="shape=mxgraph.lean_mapping.electronic_info_flow_edge;html=1;rounded=0;strokeWidth=1;labelPosition=center;verticalLabelPosition=top;align=center;verticalAlign=bottom;spacingTop=0;spacingBottom=4;fontSize=11;" parent="1" edge="1">
                    <mxGeometry width="160" relative="1" as="geometry">
                        <mxPoint x="720" y="199.5" as="sourcePoint"/>
                        <mxPoint x="880" y="199.5" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-21" value="Send object or signal" style="html=1;shape=mxgraph.infographic.ribbonSimple;notch1=0;notch2=20;align=center;verticalAlign=middle;fontSize=11;fontStyle=0;fillColor=#FFFFFF;" parent="1" vertex="1">
                    <mxGeometry x="127.5" y="370" width="142.5" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-22" value="Receive object or signal" style="html=1;shape=mxgraph.infographic.ribbonSimple;notch1=20;notch2=0;align=center;verticalAlign=middle;fontSize=11;fontStyle=0;fillColor=#FFFFFF;flipH=0;spacingRight=0;spacingLeft=14;" parent="1" vertex="1">
                    <mxGeometry x="320" y="370" width="150" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-23" value="Start" style="ellipse;fillColor=strokeColor;fontSize=11;labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=7;" parent="1" vertex="1">
                    <mxGeometry x="165" y="10" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-24" value="End" style="ellipse;html=1;shape=endState;fillColor=strokeColor;fontSize=11;labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=7;" parent="1" vertex="1">
                    <mxGeometry x="380" y="10" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-26" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=1;fontSize=11;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="k5bAv-KiF9-cGLeYmeqg-25" target="k5bAv-KiF9-cGLeYmeqg-27" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <mxPoint x="413.75" y="300" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-28" value="[Condition]" style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=11;" parent="k5bAv-KiF9-cGLeYmeqg-26" vertex="1" connectable="0">
                    <mxGeometry x="-0.8" relative="1" as="geometry">
                        <mxPoint x="28" as="offset"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-25" value="" style="rhombus;whiteSpace=wrap;html=1;labelPosition=center;verticalLabelPosition=middle;align=center;verticalAlign=middle;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="283.75" y="280" width="42.5" height="40" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-27" value="&lt;b&gt;:&lt;/b&gt;Guard statement" style="rounded=0;whiteSpace=wrap;html=1;dashed=0;fontFamily=Helvetica;fontSize=11;fontColor=rgb(0, 0, 0);align=center;strokeColor=rgb(0, 0, 0);fillColor=rgb(255, 255, 255);" parent="1" vertex="1">
                    <mxGeometry x="406.25" y="287.5" width="100" height="25" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-30" value="" style="endArrow=classic;html=1;rounded=0;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;strokeWidth=1;fontSize=11;dashed=1;" parent="1" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="127.5" y="220" as="sourcePoint"/>
                        <mxPoint x="247.5" y="220" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-31" value="Object flow" style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=11;" parent="k5bAv-KiF9-cGLeYmeqg-30" vertex="1" connectable="0">
                    <mxGeometry x="-0.65" y="1" relative="1" as="geometry">
                        <mxPoint x="29" y="-9" as="offset"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-36" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=1;fontSize=11;" parent="1" source="k5bAv-KiF9-cGLeYmeqg-32" edge="1">
                    <mxGeometry relative="1" as="geometry">
                        <mxPoint x="680" y="200" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-32" value="&lt;div style=&quot;font-size: 10px;&quot;&gt;Merge &lt;br style=&quot;font-size: 10px;&quot;&gt;&lt;/div&gt;&lt;div style=&quot;font-size: 10px;&quot;&gt;node&lt;/div&gt;" style="rhombus;whiteSpace=wrap;html=1;labelPosition=center;verticalLabelPosition=middle;align=center;verticalAlign=middle;fontSize=10;" parent="1" vertex="1">
                    <mxGeometry x="580" y="170" width="65" height="60" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-33" value="" style="endArrow=classic;html=1;rounded=0;strokeWidth=1;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-32" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="550" y="170" as="sourcePoint"/>
                        <mxPoint x="400" y="290" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-34" value="" style="endArrow=classic;html=1;rounded=0;strokeWidth=1;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-32" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="550" y="200" as="sourcePoint"/>
                        <mxPoint x="601.1184210526317" y="199.73684210526312" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-35" value="" style="endArrow=classic;html=1;rounded=0;strokeWidth=1;fontSize=11;" parent="1" target="k5bAv-KiF9-cGLeYmeqg-32" edge="1">
                    <mxGeometry width="50" height="50" relative="1" as="geometry">
                        <mxPoint x="550" y="230" as="sourcePoint"/>
                        <mxPoint x="590" y="210" as="targetPoint"/>
                    </mxGeometry>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-37" value="&lt;i&gt;or&lt;/i&gt;" style="text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;" parent="1" vertex="1">
                    <mxGeometry x="515" y="185" width="30" height="30" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-38" value="Swimlanes" style="swimlane;childLayout=stackLayout;resizeParent=1;resizeParentMax=0;horizontal=0;startSize=20;horizontalStack=0;html=1;fontSize=10;" parent="1" vertex="1">
                    <mxGeometry x="305" y="440" width="180" height="150" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-39" value="Lane 1" style="swimlane;startSize=20;horizontal=0;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-38" vertex="1">
                    <mxGeometry x="20" width="160" height="50" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-40" value="Lane 2" style="swimlane;startSize=20;horizontal=0;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-38" vertex="1">
                    <mxGeometry x="20" y="50" width="160" height="50" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-41" value="Lane 3" style="swimlane;startSize=20;horizontal=0;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-38" vertex="1">
                    <mxGeometry x="20" y="100" width="160" height="50" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-42" value="Swimlanes" style="swimlane;childLayout=stackLayout;resizeParent=1;resizeParentMax=0;startSize=20;html=1;fontSize=10;" parent="1" vertex="1">
                    <mxGeometry x="127.5" y="440" width="150" height="150" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-43" value="Lane 1" style="swimlane;startSize=20;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-42" vertex="1">
                    <mxGeometry y="20" width="50" height="130" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-44" value="Lane 2" style="swimlane;startSize=20;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-42" vertex="1">
                    <mxGeometry x="50" y="20" width="50" height="130" as="geometry"/>
                </mxCell>
                <mxCell id="k5bAv-KiF9-cGLeYmeqg-45" value="Lane 3" style="swimlane;startSize=20;html=1;fontSize=10;" parent="k5bAv-KiF9-cGLeYmeqg-42" vertex="1">
                    <mxGeometry x="100" y="20" width="50" height="130" as="geometry"/>
                </mxCell>
            </root>
        </mxGraphModel>
    </diagram>
</mxfile>

```

### 3. Sequence Diagram

**Purpose:** Show message flows between components over time

**Key Elements:**
- Lifelines: `shape=umlLifeline;`
- Activation boxes: child cells of lifelines with `perimeter=orthogonalPerimeter`
- Messages: solid/dashed arrows between activation boxes
- Fragments: `shape=umlFrame;` for `alt`, `loop`, `opt`

**Template:**
```xml
<mxGraphModel dx="985" dy="594" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1019" pageHeight="1320" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="XppZFFv2hi1EjOijFOD9-1" parent="1" style="shape=umlFrame;whiteSpace=wrap;html=1;fillColor=#f5f5f5;fontColor=#333333;strokeColor=#666666;" value="alt" vertex="1">
      <mxGeometry height="330" width="620" x="200" y="240" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-2" parent="1" style="shape=umlLifeline;participant=umlActor;perimeter=lifelinePerimeter;html=1;container=1;collapsible=0;recursiveResize=0;verticalAlign=top;spacingTop=36;outlineConnect=0;size=40;fillColor=#f8cecc;strokeColor=#b85450;" value=":Customer" vertex="1">
      <mxGeometry height="530" width="20" x="130" y="80" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-3" parent="XppZFFv2hi1EjOijFOD9-2" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#f8cecc;strokeColor=#b85450;" value="" vertex="1">
      <mxGeometry height="420" width="10" x="5" y="70" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-4" parent="1" style="shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;fillColor=#ffe6cc;strokeColor=#d79b00;" value=":SearchForm" vertex="1">
      <mxGeometry height="520" width="100" x="270" y="90" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-5" parent="XppZFFv2hi1EjOijFOD9-4" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#ffe6cc;strokeColor=#d79b00;" value="" vertex="1">
      <mxGeometry height="380" width="10" x="45" y="80" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-6" parent="XppZFFv2hi1EjOijFOD9-4" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#ffe6cc;strokeColor=#d79b00;" value="" vertex="1">
      <mxGeometry height="40" width="10" x="50" y="110" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-7" edge="1" parent="XppZFFv2hi1EjOijFOD9-4" style="edgeStyle=orthogonalEdgeStyle;html=1;align=left;spacingLeft=2;endArrow=block;rounded=0;entryX=1;entryY=0;" target="XppZFFv2hi1EjOijFOD9-6" value="1.1: validSearch()">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="80" y="100" />
          <mxPoint x="80" y="110" />
        </Array>
        <mxPoint x="55" y="100" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-8" parent="XppZFFv2hi1EjOijFOD9-4" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#ffe6cc;strokeColor=#d79b00;" value="" vertex="1">
      <mxGeometry height="40" width="10" x="50" y="380" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-9" edge="1" parent="XppZFFv2hi1EjOijFOD9-4" source="XppZFFv2hi1EjOijFOD9-5" style="edgeStyle=orthogonalEdgeStyle;html=1;align=left;spacingLeft=2;endArrow=block;rounded=0;entryX=1;entryY=0;" target="XppZFFv2hi1EjOijFOD9-8" value="1.3: displayError()">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="80" y="370" />
          <mxPoint x="80" y="380" />
        </Array>
        <mxPoint x="50" y="320" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-10" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-3" style="html=1;verticalAlign=bottom;endArrow=block;entryX=0;entryY=0;rounded=0;" target="XppZFFv2hi1EjOijFOD9-5" value="1: itemSearch(itemName)">
      <mxGeometry relative="1" as="geometry">
        <mxPoint x="245" y="170" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-11" parent="1" style="shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;fillColor=#dae8fc;strokeColor=#6c8ebf;" value=":SearchResults" vertex="1">
      <mxGeometry height="520" width="100" x="490" y="90" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-12" parent="XppZFFv2hi1EjOijFOD9-11" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#dae8fc;strokeColor=#6c8ebf;" value="" vertex="1">
      <mxGeometry height="20" width="10" x="45" y="250" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-13" parent="1" style="shape=umlLifeline;participant=umlEntity;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;verticalAlign=top;spacingTop=36;outlineConnect=0;fillColor=#e1d5e7;strokeColor=#9673a6;" value=":ItemDatabase" vertex="1">
      <mxGeometry height="520" width="40" x="660" y="90" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-14" parent="XppZFFv2hi1EjOijFOD9-13" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#e1d5e7;strokeColor=#9673a6;" value="" vertex="1">
      <mxGeometry height="40" width="10" x="15" y="180" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-15" parent="1" style="shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;fillColor=#d5e8d4;strokeColor=#82b366;" value=":ResultList" vertex="1">
      <mxGeometry height="220" width="100" x="740" y="160" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-16" parent="XppZFFv2hi1EjOijFOD9-15" style="shape=umlDestroy;whiteSpace=wrap;html=1;strokeWidth=3;" value="" vertex="1">
      <mxGeometry height="30" width="30" x="35" y="200" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-17" parent="XppZFFv2hi1EjOijFOD9-15" style="html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#d5e8d4;strokeColor=#82b366;" value="" vertex="1">
      <mxGeometry height="65" width="10" x="45" y="115" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-18" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-5" style="html=1;verticalAlign=bottom;endArrow=block;entryX=0;entryY=0;rounded=0;" target="XppZFFv2hi1EjOijFOD9-14" value="1.2: SearchItems(itemName)">
      <mxGeometry relative="1" as="geometry">
        <mxPoint x="610" y="200" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-19" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-14" style="html=1;verticalAlign=bottom;endArrow=block;entryX=0;entryY=0;rounded=0;" target="XppZFFv2hi1EjOijFOD9-17" value="1.2.1: listResults()">
      <mxGeometry relative="1" as="geometry">
        <mxPoint x="722" y="285" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-20" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-17" style="html=1;verticalAlign=bottom;endArrow=block;entryX=1;entryY=0;rounded=0;" target="XppZFFv2hi1EjOijFOD9-12" value="1.2.1.1: displayResults()">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="610" y="340" />
        </Array>
        <mxPoint x="610" y="320" as="sourcePoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-21" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-1" style="endArrow=none;dashed=1;html=1;rounded=0;entryX=1;entryY=0.576;entryDx=0;entryDy=0;entryPerimeter=0;exitX=0;exitY=0.573;exitDx=0;exitDy=0;exitPerimeter=0;" target="XppZFFv2hi1EjOijFOD9-1" value="">
      <mxGeometry height="50" relative="1" width="50" as="geometry">
        <mxPoint x="410" y="380" as="sourcePoint" />
        <mxPoint x="460" y="330" as="targetPoint" />
      </mxGeometry>
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-22" parent="1" style="text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;" value="[itemName=valid]" vertex="1">
      <mxGeometry height="20" width="110" x="200" y="270" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-23" parent="1" style="text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;" value="[else]" vertex="1">
      <mxGeometry height="20" width="40" x="200" y="430" as="geometry" />
    </mxCell>
    <mxCell id="XppZFFv2hi1EjOijFOD9-24" edge="1" parent="1" source="XppZFFv2hi1EjOijFOD9-5" style="edgeStyle=none;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=open;endFill=0;dashed=1;" target="XppZFFv2hi1EjOijFOD9-3">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="230" y="540" />
        </Array>
      </mxGeometry>
    </mxCell>
  </root>
</mxGraphModel>

```

### 4. State Diagram

**Purpose:** Show state transitions and conditions

**Key Elements:**
- States: `rounded=1;` boxes
- Start/end: `shape=ellipse;` or `shape=doubleEllipse;`
- Transitions: arrows with guard conditions

**Template:**
```xml



  



  



  
    
      
      
    

```

---

## Common Patterns

### L-Shaped Arrow (Orthogonal Routing)

For arrows that need to turn 90 degrees:

```xml

  
    
      
      
    
  

```

### Dashed Loop/Alt Fragment

For UML fragments (loop, alt, opt):

```xml

  

```

### Legend/Key

For explaining color coding and arrow types:

```xml


  


  
    
    
  


```

### Title/Header Text

```xml

  

```

---

## Best Practices

### 1. ID Naming Convention

Use descriptive, consistent IDs:

```
Good:     ll_video, ab_detector, m1_capture, e_loop_back, comp_analytics
Bad:      cell1, x, msg, arrow42, box123
```

### 2. Coordinate System

- Use `x`, `y` > 0 (no negative coordinates)
- Leave margin: start at `x=100`, `y=70` minimum
- Standard A4 page: width=827, height=1169
- Component spacing: 180–200 pixels horizontally
- Vertical spacing: 80–100 pixels between sections

### 3. Consistent Styling

- Always use the same color for the same concept
- Use `fillColor` + `strokeColor` together
- Set `html=1` on all shapes for proper text rendering
- Set `rounded=0` explicitly to avoid rounding surprises

### 4. Arrow Labeling

- Place label `value` on arrow for clarity
- Use short, descriptive labels (1–3 words)
- Labels auto-position over the arrow

### 5. Activation Boxes (Sequence Diagrams)

- Child cells of lifelines (use `parent="ll_id"`)
- Width always 10px
- Position `x` usually 45–55 within parent
- Height covers the messages for that lifeline

### 6. Routing Points

Use routing arrays for L-shaped or complex paths:

```xml

    
    

```

### 7. Avoid Overlaps

- Separate lifelines by 150–200px
- Don't overlap messages and shapes
- Use `dashed=1` and `dashPattern=8 4` for fragments/optional flows

### 8. Page Layout

```
┌─────────────────────────────────────┐
│         Title (y=20)                │
├─────────────────────────────────────┤
│  Main content area                  │
│  (x=100, y=70 to x=800, y=1050)     │
├─────────────────────────────────────┤
│  Legend (y=535+)                    │
└─────────────────────────────────────┘
```

---

## Examples

### Example 1: Minimal Component Diagram

```xml

  
    
    
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    

```

### Example 2: Activity Diagram with Branching

```xml

  
    
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    
    
    
      
    

```

---

## Quick Reference Checklist

When generating a DrawIO diagram, verify:

- [ ] Root structure: `<mxGraphModel>` → `<root>` → `<mxCell id="0" />` + `<mxCell id="1" parent="0" />`
- [ ] Page dimensions match use case (A4: 827×1169, or landscape: 1169×827)
- [ ] All shapes have unique `id` attributes
- [ ] All edges reference valid `source` and `target` IDs
- [ ] Colors are consistent across same element types
- [ ] Text is centered with `align=center;verticalAlign=middle;`
- [ ] Arrows have appropriate labels and styling
- [ ] No negative coordinates
- [ ] Lifelines are parent cells; activation boxes are children
- [ ] UML fragments use `shape=umlFrame;` and `dashed=1;`
- [ ] Titles use large font (`fontSize=14;fontStyle=1;`)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Text not visible | Add `html=1` to style; check `fontColor` vs `fillColor` contrast |
| Arrow not appearing | Verify `source` and `target` IDs exist; set `edge="1"` |
| Overlapping elements | Increase `x` or `y` spacing; use routing points for arrows |
| Lifeline activation box misaligned | Ensure it's a child of lifeline (parent="ll_id"), not parent="1" |
| Fragment border not dashed | Add `dashed=1;dashPattern=8 4;` to style |
| Text cut off | Increase `width` or `height` of shape |
| Color looks wrong | Verify hex color is 6 digits (#RRGGBB), use standard palette |

---

## File Format & Export

### Valid DrawIO File

The complete XML file must:
1. Start with `<mxGraphModel ...>` tag
2. Contain `<root>` section
3. Have at least two base cells: `<mxCell id="0" />` and `<mxCell id="1" parent="0" />`
4. End with closing `</mxGraphModel>` tag

### To Use in DrawIO

1. **File → Open** from your computer, or
2. **File → Import from → Device** (select your `.xml` file)
3. DrawIO automatically parses and renders the diagram

### Programmatic Generation Tips

- Generate IDs using slugified names: `ll_video_source`, `comp_analytics_engine`
- Use templates for common elements (lifelines, components, etc.)
- Build position maps for grid-based layouts
- Store color palette as constants/variables
- Validate all edge source/target references before output

---

## Color Palette Reference

Copy-paste ready:

```
Process:     fillColor=#d5e8d4;strokeColor=#82b366;
Perception:  fillColor=#e1d5e7;strokeColor=#9673a6;
I/O:         fillColor=#f5f5f5;strokeColor=#666666;
Config:      fillColor=#ffe6cc;strokeColor=#d79b00;
Error:       fillColor=#f8cecc;strokeColor=#b85450;
Decision:    fillColor=#fff2cc;strokeColor=#d6b656;
Text (dark): fontColor=#333333;
Text (gray): fontColor=#666666;
Border (opt):strokeColor=#666666;dashed=1;dashPattern=8 4;
```

---

## Related Resources

- [DrawIO Official Docs](https://www.diagrams.net/)
- [UML Reference](https://www.uml.org/)
- [mxGraph Documentation](https://jgraph.github.io/mxgraph/) (DrawIO's underlying library)
- [A4 Paper Dimensions](https://en.wikipedia.org/wiki/Paper_size#A_series)
